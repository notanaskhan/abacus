"""G-01-T13 annual independence against Postgres and over HTTP (G-01 AC6.1 to AC6.3; DEC-91,
DEC-381): Grace Holloway publishes the firm's statement; Kevin Osei (staff, no firm role, on no
engagement) confirms it for himself; P-07 reads `has_current_annual_confirmation`; partners and
firm admins read everyone's status with counts that foot to the seat holders; nobody confirms for
anyone else, and agents, the platform, support and client users never confirm.

Expectations come from G-01 section 3.6 and the firm-settings contract."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, date, datetime, timedelta
from typing import cast
from zoneinfo import ZoneInfo

import asyncpg
import httpx
import pytest

from abacus.api import create_app
from abacus.kernel import clock
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.errors import NotFound
from abacus.modules.identity import annual_independence as annual
from abacus.modules.identity.annual_independence import (
    AnnualConfirmationInvalid,
    StaleStatement,
)
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    configure_verifier,
    has_current_annual_confirmation,
    reset_verifier,
)
from abacus_tools.fakes.identity import FakeIdentityProvider

from .agent_tests.support import Person, Seeder
from .conftest import MigratedDatabase

FLAG = "firm_settings.v2"
CHICAGO = ZoneInfo("America/Chicago")
STATEMENT = "I am independent of the firm's attest clients.\nI hold no direct financial interest."


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


def _ctx(
    who: Person, firm_role: str | None = None, *, kind: str = "human", fresh: bool = True
) -> AuthContext:
    return AuthContext(
        tenant=TenantContext(who.tenant_id, kind, str(who.user_id)),  # pyright: ignore[reportArgumentType] -- an actor-kind code
        user_id=who.user_id,
        membership_id=uuid.uuid4(),
        firm_role=firm_role,  # pyright: ignore[reportArgumentType] -- a seeded firm role code
        mfa_at=datetime.now(UTC) - timedelta(minutes=1 if fresh else 60),
    )


class Firm:
    def __init__(self, seed: Seeder, tenant: uuid.UUID) -> None:
        self.seed = seed
        self.tenant = tenant

    async def person(self, *, firm_role: str | None = None, level: str = "staff") -> Person:
        who = await self.seed.person(self.tenant)
        await self.seed.run(
            "UPDATE memberships SET firm_role = $3, level = $4 WHERE tenant_id = $1 "
            "AND user_id = $2",
            self.tenant,
            who.user_id,
            firm_role,
            level,
        )
        return who

    async def audit(self, action: str) -> list[dict[str, object]]:
        rows = await self.seed.rows(
            "SELECT actor_kind, actor_id, target_id::text AS target_id, after_ref::text AS a "
            "FROM audit_events WHERE tenant_id = $1 AND action = $2 ORDER BY seq",
            self.tenant,
            action,
        )
        return [dict(r) for r in rows]


@pytest.fixture
async def firm(seed: Seeder) -> Firm:
    tenant = await seed.firm()
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, $2, 'true', 'test-seed', 'G-01-T13')",
        tenant,
        FLAG,
    )
    return Firm(seed, tenant)


async def _headers(seed: Seeder, idp: FakeIdentityProvider, who: Person) -> dict[str, str]:
    subject = str(await seed.value("SELECT idp_subject FROM users WHERE id = $1", who.user_id))
    return {"Authorization": f"Bearer {idp.token(subject, mfa=True)}"}


THIS_YEAR = 2026


@pytest.fixture(autouse=True)
def in_2026() -> Iterator[None]:
    with clock.frozen(datetime(2026, 9, 14, 9, 24, tzinfo=CHICAGO)):
        yield


# --- AC6.1: oneself, the statement version read --------------------------------------------------


async def test_ac6_1_kevin_confirms_the_published_statement_for_himself_over_http(
    firm: Firm, seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider
) -> None:
    grace = await firm.person(firm_role="firm_admin", level="admin")
    kevin = await firm.person()  # staff, no firm role, on no engagement
    grace_h = await _headers(seed, idp, grace)
    kevin_h = await _headers(seed, idp, kevin)

    mine = await http.get("/v1/me/independence/annual", headers=kevin_h)
    assert mine.status_code == 200, mine.text
    assert mine.json() == {
        "year": THIS_YEAR,
        "status": "not_yet",
        "decided_at": None,
        "statement": None,
    }
    early = await http.post(
        "/v1/me/independence/annual",
        headers=kevin_h,
        json={"year": THIS_YEAR, "decision": "confirmed", "statement_version": 1},
    )
    assert early.status_code == 409
    assert early.json()["detail"] == "independence_statement_missing"

    published = await http.put(
        "/v1/firm/independence/statement", headers=grace_h, json={"body": STATEMENT}
    )
    assert published.status_code == 200, published.text
    assert published.json() == {"version": 1, "body": STATEMENT}
    refused = await http.put(
        "/v1/firm/independence/statement", headers=kevin_h, json={"body": "Mine"}
    )
    assert refused.status_code == 403

    mine = await http.get("/v1/me/independence/annual", headers=kevin_h)
    assert mine.json()["statement"] == {"version": 1, "body": STATEMENT}
    confirmed = await http.post(
        "/v1/me/independence/annual",
        headers=kevin_h,
        json={"year": THIS_YEAR, "decision": "confirmed", "statement_version": 1},
    )
    assert confirmed.status_code == 201, confirmed.text
    assert confirmed.json()["decision"] == "confirmed"
    assert (await http.get("/v1/me/independence/annual", headers=kevin_h)).json()[
        "status"
    ] == "confirmed"
    assert await has_current_annual_confirmation(_ctx(kevin).tenant, kevin.user_id)
    assert await has_current_annual_confirmation(
        _ctx(kevin).tenant, kevin.user_id, date(2026, 12, 31)
    )
    assert not await has_current_annual_confirmation(
        _ctx(kevin).tenant, kevin.user_id, date(2027, 1, 1)
    )
    [row] = await firm.audit("independence.annual_confirmed")
    assert (row["actor_kind"], row["actor_id"], row["target_id"]) == (
        "human",
        str(kevin.user_id),
        str(kevin.user_id),
    )

    # Someone else's id can't be named: the body has no user id and refuses unknown fields.
    other = await http.post(
        "/v1/me/independence/annual",
        headers=grace_h,
        json={
            "year": THIS_YEAR,
            "decision": "confirmed",
            "statement_version": 1,
            "user_id": str(kevin.user_id),
        },
    )
    assert other.status_code == 422


async def test_ac6_1_a_newer_statement_makes_an_old_version_stale(firm: Firm) -> None:
    grace = await firm.person(firm_role="firm_admin", level="admin")
    kevin = await firm.person()
    first = await annual.publish_statement(_ctx(grace, "firm_admin"), STATEMENT)
    second = await annual.publish_statement(_ctx(grace, "firm_admin"), STATEMENT + " Amended.")
    assert (first.version, second.version) == (1, 2)
    with pytest.raises(StaleStatement):
        await annual.record(
            _ctx(kevin), year=THIS_YEAR, decision="confirmed", statement_version=1, note=None
        )
    done = await annual.record(
        _ctx(kevin), year=THIS_YEAR, decision="confirmed", statement_version=2, note=None
    )
    assert done.decision == "confirmed"


async def test_ac6_1_a_decline_needs_a_note_and_only_this_year_is_answered(firm: Firm) -> None:
    grace = await firm.person(firm_role="firm_admin", level="admin")
    kevin = await firm.person()
    await annual.publish_statement(_ctx(grace, "firm_admin"), STATEMENT)
    with pytest.raises(AnnualConfirmationInvalid):
        await annual.record(
            _ctx(kevin), year=THIS_YEAR, decision="declined", statement_version=1, note="  "
        )
    with pytest.raises(AnnualConfirmationInvalid):
        await annual.record(
            _ctx(kevin), year=2027, decision="confirmed", statement_version=1, note=None
        )
    await annual.record(
        _ctx(kevin),
        year=THIS_YEAR,
        decision="declined",
        statement_version=1,
        note="Spouse holds shares in a client",
    )
    assert not await has_current_annual_confirmation(_ctx(kevin).tenant, kevin.user_id)
    # The newest answer wins: a decline can become a confirmation.
    await annual.record(
        _ctx(kevin), year=THIS_YEAR, decision="confirmed", statement_version=1, note=None
    )
    assert await has_current_annual_confirmation(_ctx(kevin).tenant, kevin.user_id)
    assert len(await firm.audit("independence.annual_declined")) == 1


async def test_ac6_1_agents_the_platform_support_and_client_users_never_confirm(
    firm: Firm,
) -> None:
    grace = await firm.person(firm_role="firm_admin", level="admin")
    kevin = await firm.person()
    await annual.publish_statement(_ctx(grace, "firm_admin"), STATEMENT)
    for kind in ("agent", "system"):
        with pytest.raises(Forbidden):
            await annual.record(
                _ctx(kevin, kind=kind),
                year=THIS_YEAR,
                decision="confirmed",
                statement_version=1,
                note=None,
            )
    support = _ctx(kevin, "platform_support", kind="support")
    with pytest.raises(Forbidden):
        await annual.record(
            support, year=THIS_YEAR, decision="confirmed", statement_version=1, note=None
        )
    client_user = AuthContext(
        tenant=TenantContext(firm.tenant, "human", str(kevin.user_id)),
        user_id=kevin.user_id,
        membership_id=uuid.uuid4(),
        firm_role=None,
        mfa_at=datetime.now(UTC),
        client=True,
    )
    with pytest.raises(Forbidden):
        await annual.record(
            client_user, year=THIS_YEAR, decision="confirmed", statement_version=1, note=None
        )
    with pytest.raises(Forbidden):
        await annual.publish_statement(_ctx(grace, "firm_admin", kind="agent"), "Agent text")
    # The table refuses a non-human row whatever the code does (INV-1).
    with pytest.raises(asyncpg.CheckViolationError):
        await firm.seed.as_actor(
            firm.tenant,
            ("agent", "agent:test"),
            "INSERT INTO independence_annual_confirmations (tenant_id, user_id, year, decision, "
            "statement_version) VALUES ($1, $2, 2026, 'confirmed', 1)",
            firm.tenant,
            kevin.user_id,
        )
    assert await firm.audit("independence.annual_confirmed") == []


async def test_ac6_1_confirmations_are_insert_only(firm: Firm) -> None:
    grace = await firm.person(firm_role="firm_admin", level="admin")
    kevin = await firm.person()
    await annual.publish_statement(_ctx(grace, "firm_admin"), STATEMENT)
    await annual.record(
        _ctx(kevin), year=THIS_YEAR, decision="confirmed", statement_version=1, note=None
    )
    for sql in (
        "UPDATE independence_annual_confirmations SET decision = 'declined', note = 'x' "
        "WHERE tenant_id = $1",
        "DELETE FROM independence_annual_confirmations WHERE tenant_id = $1",
        "UPDATE independence_statements SET body = 'x' WHERE tenant_id = $1",
    ):
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await firm.seed.run(sql, firm.tenant)


# --- AC6.3: who reads the list ------------------------------------------------------------------


async def test_ac6_3_the_list_foots_to_the_seat_holders_for_partners_and_admins(
    firm: Firm, seed: Seeder
) -> None:
    grace = await firm.person(firm_role="firm_admin", level="admin")
    margaret = await firm.person(level="partner")
    kevin = await firm.person()
    lena = await firm.person(level="seasonal")
    gone = await firm.person()
    await seed.revoke(gone)
    await annual.publish_statement(_ctx(grace, "firm_admin"), STATEMENT)
    await annual.record(
        _ctx(kevin), year=THIS_YEAR, decision="confirmed", statement_version=1, note=None
    )
    await annual.record(
        _ctx(lena), year=THIS_YEAR, decision="declined", statement_version=1, note="Relative"
    )
    for reader in (_ctx(grace, "firm_admin"), _ctx(margaret)):
        found = await annual.annual(reader, THIS_YEAR)
        by_user = {r.user_id: r for r in found.rows}
        assert set(by_user) == {grace.user_id, margaret.user_id, kevin.user_id, lena.user_id}
        assert by_user[kevin.user_id].status == "confirmed"
        assert by_user[kevin.user_id].decided_at is not None
        assert (by_user[lena.user_id].status, by_user[lena.user_id].note) == (
            "declined",
            "Relative",
        )
        assert by_user[grace.user_id].status == "not_yet"
        assert found.counts == {"confirmed": 1, "not_yet": 2, "declined": 1}
        assert sum(found.counts.values()) == len(found.rows)
    assert (await annual.annual(_ctx(grace, "firm_admin"), 2025)).counts == {
        "confirmed": 0,
        "not_yet": 4,
        "declined": 0,
    }
    with pytest.raises(NotFound):
        await annual.annual(_ctx(kevin), THIS_YEAR)  # staff: nothing to see (ADR-024)


async def test_another_firm_reads_and_counts_nothing_of_this_one(firm: Firm, seed: Seeder) -> None:
    grace = await firm.person(firm_role="firm_admin", level="admin")
    kevin = await firm.person()
    await annual.publish_statement(_ctx(grace, "firm_admin"), STATEMENT)
    await annual.record(
        _ctx(kevin), year=THIS_YEAR, decision="confirmed", statement_version=1, note=None
    )
    other = Firm(seed, await seed.firm())
    their_admin = await other.person(firm_role="firm_admin", level="admin")
    found = await annual.annual(_ctx(their_admin, "firm_admin"), THIS_YEAR)
    assert [r.user_id for r in found.rows] == [their_admin.user_id]
    assert await annual.statement(_ctx(their_admin, "firm_admin")) is None
    # Kevin's id in the other firm answers nothing (no membership there).
    assert not await has_current_annual_confirmation(
        TenantContext(other.tenant, "system", "probe"), kevin.user_id
    )
    assert (
        cast(
            int,
            await seed.value(
                "SELECT count(*) FROM independence_annual_confirmations WHERE tenant_id = $1",
                other.tenant,
            ),
        )
        == 0
    )
