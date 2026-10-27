"""G-01-T13 the seasonal access-end job against Postgres (G-01 AC4.5, R-7; DEC-381): Grace Holloway
sets the Seasonal group's date to Oct 31, 2026; on Oct 24 firm admins are told once; at Nov 1,
00:20 CT the job deactivates the five seasonal members with reason `access_ended`, as the system
on behalf of Grace; a second run does nothing; a member whose date moved is kept; another firm's
members are untouched; the firm's last firm admin is never ended.

Expectations come from G-01 sections 3.4 and 4.4, not from the implementation."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, date, datetime, timedelta
from typing import cast
from zoneinfo import ZoneInfo

import httpx
import pytest

from abacus.api import create_app
from abacus.kernel import clock
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.modules.identity import access_end, people
from abacus.modules.identity.api import (
    SCHEDULES,
    AccessEndSweepWorkflow,
    AuthContext,
    configure_verifier,
    reset_verifier,
)
from abacus.modules.notifications.api import SUBSCRIPTIONS as NOTIFY
from abacus_tools.fakes.identity import FakeIdentityProvider

from .agent_tests.support import Person, Seeder
from .conftest import MigratedDatabase

CHICAGO = ZoneInfo("America/Chicago")
OCT_31 = date(2026, 10, 31)


@pytest.fixture(autouse=True)
async def engines(
    migrated_db: MigratedDatabase, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[None]:
    monkeypatch.setenv("ABACUS_IDENTITY_DATABASE_URL", migrated_db.identity_url)
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()
    settings.cache_clear()


@pytest.fixture
def seed(migrated_db: MigratedDatabase) -> Seeder:
    return Seeder(migrated_db.superuser_dsn)


def _ctx(who: Person, firm_role: str | None = None) -> AuthContext:
    return AuthContext(
        tenant=TenantContext(who.tenant_id, "human", str(who.user_id)),
        user_id=who.user_id,
        membership_id=uuid.uuid4(),
        firm_role=firm_role,  # pyright: ignore[reportArgumentType] -- a seeded firm role code
        mfa_at=datetime.now(UTC) - timedelta(minutes=1),
    )


class Firm:
    def __init__(self, seed: Seeder, tenant: uuid.UUID) -> None:
        self.seed = seed
        self.tenant = tenant

    async def person(self, *, firm_role: str | None = None, level: str = "staff") -> Person:
        who = await self.seed.person(self.tenant)
        await self.seed.run(
            "UPDATE memberships SET firm_role = $3, level = $4, "
            "access_ends_on = CASE WHEN $4 = 'seasonal' THEN DATE '2026-12-31' END "
            "WHERE tenant_id = $1 AND user_id = $2",
            self.tenant,
            who.user_id,
            firm_role,
            level,
        )
        return who

    async def status(self, who: Person) -> tuple[str, str | None, uuid.UUID | None]:
        [row] = await self.seed.rows(
            "SELECT status, revoked_reason, revoked_on_behalf_of FROM memberships "
            "WHERE tenant_id = $1 AND user_id = $2",
            self.tenant,
            who.user_id,
        )
        return (row["status"], row["revoked_reason"], row["revoked_on_behalf_of"])

    async def audit(self, action: str) -> list[dict[str, object]]:
        rows = await self.seed.rows(
            "SELECT actor_kind, on_behalf_of_user_id, target_id::text AS target_id, "
            "after_ref::text AS a FROM audit_events WHERE tenant_id = $1 AND action = $2 "
            "ORDER BY seq",
            self.tenant,
            action,
        )
        return [dict(r) for r in rows]

    async def outbox(self, event_type: str) -> list[dict[str, object]]:
        rows = await self.seed.rows(
            "SELECT payload FROM outbox WHERE tenant_id = $1 AND event_type = $2 "
            "ORDER BY occurred_at, id",
            self.tenant,
            event_type,
        )
        return [
            json.loads(r["payload"]) if isinstance(r["payload"], str) else dict(r["payload"])
            for r in rows
        ]


@pytest.fixture
async def firm(seed: Seeder) -> Firm:
    tenant = await seed.firm()
    # The firm's own time zone decides its midnight (`kernel.clock`).
    await seed.run("UPDATE firms SET time_zone = 'America/Chicago' WHERE tenant_id = $1", tenant)
    return Firm(seed, tenant)


async def _season(firm: Firm) -> tuple[Person, list[Person], Person]:
    grace = await firm.person(firm_role="firm_admin", level="admin")
    seasonal = [await firm.person(level="seasonal") for _ in range(5)]
    kevin = await firm.person()
    ends = await people.set_seasonal_access_ends(_ctx(grace, "firm_admin"), OCT_31)
    assert ends.members == 5
    return grace, seasonal, kevin


def _at(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=CHICAGO)


async def test_ac4_5_seven_days_ahead_firm_admins_are_told_once(firm: Firm) -> None:
    await _season(firm)
    with clock.frozen(_at(date(2026, 10, 23), 12)):
        assert await access_end.sweep_firm(firm.tenant) == (0, 0)  # eight days ahead
    with clock.frozen(_at(date(2026, 10, 24), 0, 20)):
        assert await access_end.sweep_firm(firm.tenant) == (0, 1)
        assert await access_end.sweep_firm(firm.tenant) == (0, 0)  # once per date
    with clock.frozen(_at(date(2026, 10, 30), 9)):
        assert await access_end.sweep_firm(firm.tenant) == (0, 0)
    [notice] = await firm.outbox("membership.access_ending")
    assert (notice["access_ends_on"], notice["members"]) == ("2026-10-31", 5)
    assert "membership.access_ending" in NOTIFY  # fanned out to firm admins (C16)
    assert len(await firm.audit("membership.access_ending_notified")) == 1


async def test_ac4_5_after_midnight_the_five_are_deactivated_on_behalf_of_grace(
    firm: Firm,
) -> None:
    grace, seasonal, kevin = await _season(firm)
    with clock.frozen(_at(OCT_31, 23, 50)):
        assert (await access_end.sweep_firm(firm.tenant))[0] == 0  # still Oct 31 in Chicago
    with clock.frozen(_at(date(2026, 11, 1), 0, 20)):
        ended, _ = await access_end.sweep_firm(firm.tenant)
    assert ended == 5
    for who in seasonal:
        assert await firm.status(who) == ("revoked", "access_ended", grace.user_id)
    assert (await firm.status(kevin))[0] == "active"
    assert (await firm.status(grace))[0] == "active"
    rows = await firm.audit("membership.deactivated")
    assert len(rows) == 5
    assert {(r["actor_kind"], r["on_behalf_of_user_id"]) for r in rows} == {
        ("system", grace.user_id)
    }
    assert {r["target_id"] for r in rows} == {str(p.user_id) for p in seasonal}
    deactivated = [str(p["user_id"]) for p in await firm.outbox("membership.deactivated")]
    assert sorted(deactivated) == sorted(str(p.user_id) for p in seasonal)
    # ADM-02e reads them "Deactivated Oct 31" and the seats free (41 of 46 in the seed).
    with clock.frozen(_at(date(2026, 11, 2), 9)):
        page = await people.staff_page(_ctx(grace, "firm_admin"), people.StaffFilters())
    gone = [r for r in page.items if r.status == "deactivated"]
    assert {r.deactivated_on for r in gone} == {OCT_31}
    assert len(gone) == 5


async def test_ac4_5_the_job_is_idempotent(firm: Firm) -> None:
    await _season(firm)
    with clock.frozen(_at(date(2026, 11, 2), 1)):
        assert (await access_end.sweep_firm(firm.tenant))[0] == 5
        assert await access_end.sweep_firm(firm.tenant) == (0, 0)
    assert len(await firm.audit("membership.deactivated")) == 5


async def test_ac4_5_a_moved_date_is_respected_and_the_last_admin_is_kept(firm: Firm) -> None:
    grace, seasonal, _ = await _season(firm)
    moved = seasonal[0]
    await firm.seed.run(
        "UPDATE memberships SET access_ends_on = DATE '2026-11-30' WHERE user_id = $1",
        moved.user_id,
    )
    # The only firm admin carries an end date too: the job never leaves the firm without one.
    await firm.seed.run(
        "UPDATE memberships SET access_ends_on = DATE '2026-10-01' WHERE user_id = $1",
        grace.user_id,
    )
    with clock.frozen(_at(date(2026, 11, 1), 0, 20)):
        ended, _ = await access_end.sweep_firm(firm.tenant)
    assert ended == 4
    assert (await firm.status(moved))[0] == "active"
    assert (await firm.status(grace))[0] == "active"


async def test_another_firms_members_are_untouched(firm: Firm, seed: Seeder) -> None:
    await _season(firm)
    other = Firm(seed, await seed.firm())
    theirs = await other.person(level="seasonal")  # ends Dec 31
    with clock.frozen(_at(date(2026, 11, 1), 0, 20)):
        swept = await access_end.sweep_access_ends()
    assert swept.ended >= 5
    assert (await other.status(theirs))[0] == "active"
    assert await other.audit("membership.deactivated") == []


def test_the_job_is_an_hourly_background_schedule() -> None:
    # G-02-T14 adds identity's second Schedule, the daily staff-session purge.
    assert [j.id for j in SCHEDULES] == ["access_end:platform", "auth_session_purge:platform"]
    [job] = [j for j in SCHEDULES if j.id == "access_end:platform"]
    assert (job.id, job.every, job.workflow) == (
        "access_end:platform",
        timedelta(hours=1),
        AccessEndSweepWorkflow,
    )


# --- security review M3 (DEC-383): access ends at request time, whatever the job did --


@pytest.fixture
def idp() -> Iterator[FakeIdentityProvider]:
    provider = FakeIdentityProvider()
    configure_verifier(provider.verifier())
    yield provider
    reset_verifier()


@pytest.fixture
async def http(idp: FakeIdentityProvider) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=create_app(), raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def _get(firm: Firm, http: httpx.AsyncClient, idp: FakeIdentityProvider, who: Person) -> int:
    subject = str(
        await firm.seed.value("SELECT idp_subject FROM users WHERE id = $1", who.user_id)
    )
    response = await http.get(
        "/v1/engagements",
        headers={
            "Authorization": f"Bearer {idp.token(subject, mfa=True)}",
            "X-Abacus-Tenant": str(firm.tenant),
        },
    )
    return response.status_code


async def test_m3_a_past_access_end_refuses_requests_even_if_the_job_never_ran(
    firm: Firm, http: httpx.AsyncClient, idp: FakeIdentityProvider
) -> None:
    _, seasonal, kevin = await _season(firm)
    lena = seasonal[0]
    with clock.frozen(_at(OCT_31, 23, 50)):
        assert await _get(firm, http, idp, lena) == 200  # the last day of access, in Chicago
    with clock.frozen(_at(date(2026, 11, 1), 0, 20)):
        assert await _get(firm, http, idp, lena) == 403  # no sweep has run
        assert await _get(firm, http, idp, kevin) == 200  # no end date
    assert (await firm.status(lena))[0] == "active"  # the state change stays the job's


async def test_m3_a_failing_firm_is_logged_and_counted_and_the_others_still_run(
    firm: Firm, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    await _season(firm)
    real = access_end.sweep_firm

    async def flaky(tenant_id: uuid.UUID) -> tuple[int, int]:
        if tenant_id == firm.tenant:
            raise RuntimeError("boom")
        return await real(tenant_id)

    monkeypatch.setattr(access_end, "sweep_firm", flaky)
    with clock.frozen(_at(date(2026, 11, 1), 0, 20)):
        swept = await access_end.sweep_access_ends()
    assert swept.failed_firms == 1
    assert (await firm.status(await firm.person(level="seasonal")))[0] == "active"


def test_m3_no_successful_sweep_in_two_runs_is_stale() -> None:
    assert access_end.stale([False, False])
    assert not access_end.stale([True, False])
    assert not access_end.stale([False, True])
    assert not access_end.stale([False])  # one failed run is not two hours
    assert not access_end.stale([])


async def test_m3_an_agent_acting_for_someone_whose_access_ended_is_refused(firm: Firm) -> None:
    """Re-review: an agent is checked against its initiator, so a run started by a person whose
    end date has passed is refused on its next action, though no sweep has run."""
    from abacus.modules.identity import context
    from abacus.modules.identity.api import AgentContext, Forbidden, Resource, authorise

    _, seasonal, _ = await _season(firm)
    lena = seasonal[0]
    client = await firm.seed.value(
        "INSERT INTO clients (tenant_id, name) VALUES ($1, 'Probe client') RETURNING id",
        firm.tenant,
    )
    entity = await firm.seed.value(
        "INSERT INTO client_entities (tenant_id, client_id, name) VALUES ($1, $2, 'Probe') "
        "RETURNING id",
        firm.tenant,
        client,
    )
    engagement = cast(
        uuid.UUID,
        await firm.seed.value(
            "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, type, status, "
            "fiscal_period_start, fiscal_period_end, created_by) VALUES ($1, $2, $3, 'Probe', "
            "'tax_compliance', 'active', '2025-01-01', '2025-12-31', $4) RETURNING id",
            firm.tenant,
            client,
            entity,
            lena.user_id,
        ),
    )
    await firm.seed.open(firm.tenant, engagement)
    await firm.seed.member(engagement, lena, "staff")
    run_id = uuid.uuid4()
    agent = AgentContext(
        tenant=TenantContext(firm.tenant, "agent", f"agent:evidence.screener:{run_id}"),
        agent_id="evidence.screener",
        agent_run_id=run_id,
        engagement_id=engagement,
        task_scope=frozenset({"screening.run"}),
        initiator=_ctx(lena),
        issued_by=context._ISSUER,  # pyright: ignore[reportPrivateUsage] -- an agent run's context
    )
    resource = Resource.engagement(firm.tenant, engagement, archived=False)
    with clock.frozen(_at(OCT_31, 23, 50)):
        await authorise(agent, "screening.run", resource)  # the last day: still allowed
    with clock.frozen(_at(date(2026, 11, 1), 0, 20)), pytest.raises(Forbidden) as refused:
        await authorise(agent, "screening.run", resource)
    assert refused.value.layer == "delegation"
    assert (await firm.status(lena))[0] == "active"  # no sweep ran


async def test_m3_me_stops_listing_a_firm_whose_access_ended(
    firm: Firm, http: httpx.AsyncClient, idp: FakeIdentityProvider
) -> None:
    _, seasonal, kevin = await _season(firm)
    lena = seasonal[0]

    async def firms_of(who: Person) -> list[str]:
        subject = str(
            await firm.seed.value("SELECT idp_subject FROM users WHERE id = $1", who.user_id)
        )
        response = await http.get(
            "/v1/me", headers={"Authorization": f"Bearer {idp.token(subject, mfa=True)}"}
        )
        assert response.status_code == 200, response.text
        body = response.json()
        return [str(m["tenant_id"]) for m in body["memberships"]]

    with clock.frozen(_at(OCT_31, 23, 50)):
        assert await firms_of(lena) == [str(firm.tenant)]
    with clock.frozen(_at(date(2026, 11, 1), 0, 20)):
        assert await firms_of(lena) == []
        assert await firms_of(kevin) == [str(firm.tenant)]
