"""G-01-T13 the seasonal access-end job against Postgres (G-01 AC4.5, R-7; DEC-381): Grace Holloway
sets the Seasonal group's date to Oct 31, 2026; on Oct 24 firm admins are told once; at Nov 1,
00:20 CT the job deactivates the five seasonal members with reason `access_ended`, as the system
on behalf of Grace; a second run does nothing; a member whose date moved is kept; another firm's
members are untouched; the firm's last firm admin is never ended.

Expectations come from G-01 sections 3.4 and 4.4, not from the implementation."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from abacus.kernel import clock
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.modules.identity import access_end, people
from abacus.modules.identity.api import SCHEDULES, AccessEndSweepWorkflow, AuthContext
from abacus.modules.notifications.api import SUBSCRIPTIONS as NOTIFY

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
    [job] = SCHEDULES
    assert (job.id, job.every, job.workflow) == (
        "access_end:platform",
        timedelta(hours=1),
        AccessEndSweepWorkflow,
    )
