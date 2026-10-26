"""Q-03-T044 against Postgres: a load profile builds synthetic firms through the services and the
bootstrap the scenario loader uses, with an audit row per write; a second run writes nothing.

A reduced firm shape keeps the run short; `test_q03t044_load_content.py` holds the Brightwater
size of the real profiles.
"""

from __future__ import annotations

import pytest

from abacus.kernel.db import configure_engine
from abacus_tools.synthetic import fleet

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio

SMALL = fleet.FirmShape(
    seats=7, clients=5, audits=3, requests_per_audit=4, portal_people_per_audit=2
)


async def _count(seed: Seeder, sql: str, *args: object) -> int:
    return int(str(await seed.value(sql, *args)))


async def test_ac_x1_builds_one_synthetic_firm_once(migrated_db: MigratedDatabase) -> None:
    configure_engine(migrated_db.app_url)
    seed = Seeder(migrated_db.superuser_dsn)
    [firm] = fleet.plan("x1", SMALL)
    tenant = firm.tenant

    first = await fleet.load(migrated_db.superuser_dsn, "x1", shape=SMALL)
    assert first.firms == 1 and first.skipped == 0
    assert await seed.value("SELECT synthetic FROM firms WHERE tenant_id = $1", tenant) is True
    counts = {
        "offices": "SELECT count(*) FROM offices WHERE tenant_id = $1",
        "staff": "SELECT count(*) FROM memberships WHERE tenant_id = $1 AND kind = 'staff'",
        "clients": "SELECT count(*) FROM clients WHERE tenant_id = $1",
        "engagements": "SELECT count(*) FROM engagements WHERE tenant_id = $1",
        "requests": "SELECT count(*) FROM request_items WHERE tenant_id = $1",
        "client people": (
            "SELECT count(*) FROM memberships WHERE tenant_id = $1 AND kind = 'client'"
        ),
        "grants": "SELECT count(*) FROM client_access_grants WHERE tenant_id = $1",
    }
    found = {name: await _count(seed, sql, tenant) for name, sql in counts.items()}
    assert found == {
        "offices": 3,
        "staff": SMALL.seats,
        "clients": SMALL.clients,
        "engagements": SMALL.audits,
        "requests": SMALL.audits * SMALL.requests_per_audit,
        "client people": SMALL.audits * SMALL.portal_people_per_audit,
        "grants": SMALL.audits * SMALL.portal_people_per_audit,
    }
    members = await _count(
        seed, "SELECT count(*) FROM engagement_members WHERE tenant_id = $1", tenant
    )
    assert members == SMALL.audits * 4
    flags = await seed.rows(
        "SELECT flag FROM feature_flag_states WHERE tenant_id = $1 AND value = 'true'", tenant
    )
    assert {"portal.sign_in_v2", "portal.home_v2"} <= {r["flag"] for r in flags}
    # Every bootstrapped write carries its audit row; clients carry the service's own.
    traced = await _count(
        seed,
        "SELECT count(DISTINCT trace_id) FROM audit_events WHERE tenant_id = $1 "
        "AND trace_id = ANY($2::text[])",
        tenant,
        [fleet.trace_hex(firm, s) for s in ("firm", "office:Chicago", "seat:0", "pbc:0")],
    )
    assert traced == 4
    created = await _count(
        seed,
        "SELECT count(*) FROM audit_events WHERE tenant_id = $1 AND action = 'client.created'",
        tenant,
    )
    assert created == SMALL.clients

    audits = await _count(seed, "SELECT count(*) FROM audit_events WHERE tenant_id = $1", tenant)
    again = await fleet.load(migrated_db.superuser_dsn, "x1", shape=SMALL)
    assert again.written == 0 and again.skipped == first.written
    assert audits == await _count(
        seed, "SELECT count(*) FROM audit_events WHERE tenant_id = $1", tenant
    )


async def test_ac_a_fleet_id_held_by_a_real_firm_is_refused(
    migrated_db: MigratedDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    configure_engine(migrated_db.app_url)
    seed = Seeder(migrated_db.superuser_dsn)
    held = fleet.Firm(999, SMALL)

    def only_held(profile: str, shape: fleet.FirmShape | None = None) -> tuple[fleet.Firm, ...]:
        return (held,)

    monkeypatch.setattr(fleet, "plan", only_held)
    await seed.run(
        "INSERT INTO firms (tenant_id, name, synthetic, region, time_zone) "
        "VALUES ($1, 'A real firm', false, 'us', 'America/Chicago') ON CONFLICT DO NOTHING",
        held.tenant,
    )
    with pytest.raises(fleet.LoadRefused, match="not synthetic"):
        await fleet.load(migrated_db.superuser_dsn, "x1", shape=SMALL)
    assert (
        await _count(seed, "SELECT count(*) FROM offices WHERE tenant_id = $1", held.tenant) == 0
    )


def _only(firm: fleet.Firm, monkeypatch: pytest.MonkeyPatch) -> None:
    def planned(profile: str, shape: fleet.FirmShape | None = None) -> tuple[fleet.Firm, ...]:
        return (firm,)

    monkeypatch.setattr(fleet, "plan", planned)


async def test_ac_as_the_owner_role_under_rls_a_rerun_writes_nothing(
    migrated_db: MigratedDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Security review (DEC-455): the owner role does not bypass row-level security, so every
    pre-check reads as the firm; a laptop superuser would hide a blind check."""
    configure_engine(migrated_db.app_url)
    seed = Seeder(migrated_db.superuser_dsn)
    firm = fleet.Firm(997, SMALL)
    _only(firm, monkeypatch)
    first = await fleet.load(migrated_db.owner_url, "x1", shape=SMALL)
    assert first.written > 0 and first.skipped == 0
    audits = await _count(
        seed, "SELECT count(*) FROM audit_events WHERE tenant_id = $1", firm.tenant
    )
    again = await fleet.load(migrated_db.owner_url, "x1", shape=SMALL)
    assert (again.written, again.skipped) == (0, first.written)
    assert audits == await _count(
        seed, "SELECT count(*) FROM audit_events WHERE tenant_id = $1", firm.tenant
    )


async def test_ac_as_the_owner_role_a_non_synthetic_firm_is_refused(
    migrated_db: MigratedDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    configure_engine(migrated_db.app_url)
    seed = Seeder(migrated_db.superuser_dsn)
    held = fleet.Firm(996, SMALL)
    _only(held, monkeypatch)
    await seed.run(
        "INSERT INTO firms (tenant_id, name, synthetic, region, time_zone) "
        "VALUES ($1, 'A real firm', false, 'us', 'America/Chicago') ON CONFLICT DO NOTHING",
        held.tenant,
    )
    with pytest.raises(fleet.LoadRefused, match="not synthetic"):
        await fleet.load(migrated_db.owner_url, "x1", shape=SMALL)
    assert (
        await _count(seed, "SELECT count(*) FROM offices WHERE tenant_id = $1", held.tenant) == 0
    )
