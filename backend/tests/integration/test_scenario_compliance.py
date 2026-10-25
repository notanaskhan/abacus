"""Q-02-T39 against Postgres: E0 loaded with the `compliance` slice reads, on Mon Sep 14, 2026 at
9:24 AM CT, what the golden (`tests/golden/scenario/brightwater_hale/compliance_e0.yaml`) says:
INC-2026-005 at day 4 of 30 with notice due Sat Oct 10, two active holds placed by Victor Hammond
and Neil Ashcroft, and FIL-02a's eight firm policies with no legal floor seeded. Everything went
through `evidence.api` and `platform.api` as the named people; a second load writes nothing.

The load gets its own database: the session's `migrated_db` holds the loader test's E0. Each test
loads for itself (the load is idempotent), so the tests hold under xdist workers."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from datetime import date, datetime
from pathlib import Path
from typing import cast
from uuid import UUID, uuid4

import pytest
import yaml

import abacus.modules.organisations.api  # registers member teams and the office list
from abacus.kernel import clock
from abacus.kernel.clock import system_now
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.modules.evidence.api import effective_policies, list_holds
from abacus.modules.identity.api import AuthContext
from abacus.modules.platform.api import CLOCK_DAYS, clock_day
from abacus_tools.quality.schema_check import Database, provisioned_database
from abacus_tools.synthetic.scenarios.brightwater_hale import loader
from abacus_tools.synthetic.scenarios.brightwater_hale.epochs import DEMO_INSTANT
from abacus_tools.synthetic.scenarios.brightwater_hale.prng import stable_id

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

assert abacus.modules.organisations.api
pytestmark = pytest.mark.asyncio
TENANT = loader.TENANT
GOLDEN = Path(__file__).parents[1] / "golden/scenario/brightwater_hale/compliance_e0.yaml"


@pytest.fixture(scope="module")
def own_db(migrated_db: MigratedDatabase) -> Iterator[Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database
    configure_engine(migrated_db.app_url)  # hand the session's database back to later tests


@pytest.fixture
async def loaded(own_db: Database, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[Database]:
    monkeypatch.setenv("ABACUS_IDENTITY_DATABASE_URL", own_db.identity_url)
    settings.cache_clear()
    await dispose_engine()  # the identity engine reads the new URL when next asked
    configure_engine(own_db.app_url)
    await loader.load(own_db.superuser_dsn, "E0", slices=("compliance",), wait=False)
    yield own_db
    await dispose_engine()
    settings.cache_clear()


def _golden() -> dict[str, object]:
    return cast(dict[str, object], yaml.safe_load(GOLDEN.read_text(encoding="utf-8")))


def _felix() -> AuthContext:
    user = UUID(stable_id("user:felix-andersen"))
    return AuthContext(
        TenantContext(TENANT, "human", str(user)), user, uuid4(), "security_admin", system_now()
    )


async def _incident(seed: Seeder) -> dict[str, object]:
    (row,) = await seed.rows(
        "SELECT ref, title, discovered_at, ftc_notify_by, notification_event, created_by "
        "FROM security_incidents WHERE tenant_id = $1",
        TENANT,
    )
    return dict(row)


async def test_e0_reads_day_4_of_30_and_notify_by_oct_10(loaded: Database) -> None:
    golden = cast(dict[str, object], _golden()["incident"])
    incident = await _incident(Seeder(loaded.superuser_dsn))
    assert incident["title"] == golden["title"]
    assert incident["ftc_notify_by"] == date.fromisoformat(str(golden["ftc_notify_by"]))
    assert incident["notification_event"] is golden["notification_event"]
    assert incident["created_by"] == UUID(stable_id("user:felix-andersen"))
    discovered = cast(datetime, incident["discovered_at"])
    assert discovered.astimezone(DEMO_INSTANT.tzinfo).date() == date(2026, 9, 10)
    day = clock_day(discovered, "America/Chicago", DEMO_INSTANT.date())
    assert (day, CLOCK_DAYS) == (golden["clock_day"], golden["clock_days"])


async def test_e0_reads_two_active_holds_by_victor_hammond_and_neil_ashcroft(
    loaded: Database,
) -> None:
    golden = cast(dict[str, object], _golden()["holds"])
    with clock.frozen(DEMO_INSTANT):
        holds = await list_holds(_felix())
    assert [h.status for h in holds] == ["active"] * cast(int, golden["active"])
    placed = {(h.client_id, h.tax_year, h.placed_by, h.reason_code, h.scope_kind) for h in holds}
    assert placed == {
        (
            UUID(stable_id("client:wren-and-avery-collins")),
            2023,
            UUID(stable_id("user:victor-hammond")),
            "irs_examination",
            "client_tax_year",
        ),
        (
            UUID(stable_id("client:meridian-tool-and-die-inc")),
            2024,
            UUID(stable_id("user:neil-ashcroft")),
            "regulatory_inquiry",
            "client_tax_year",
        ),
    }


async def test_e0_reads_fil02as_eight_firm_policies_without_a_seeded_floor(
    loaded: Database,
) -> None:
    golden = cast(dict[str, object], _golden()["policies"])
    with clock.frozen(DEMO_INSTANT):
        policies = await effective_policies(_felix())
    assert len(policies) == golden["count"]
    assert {str(p.firm_years.normalize()) for p in policies} == {golden["firm_years"]}
    assert [p.record_type for p in policies if p.lock] == golden["locked"]
    assert all(p.source == "policy" and p.legal_floor_years is None for p in policies)
    seed = Seeder(loaded.superuser_dsn)
    assert await seed.rows("SELECT 1 FROM retention_floors") == []  # DEC-71: never seeded


async def test_every_write_names_its_person_and_a_second_load_writes_nothing(
    loaded: Database,
) -> None:
    seed = Seeder(loaded.superuser_dsn)
    rows = await seed.rows(
        "SELECT action, actor_kind, actor_id FROM audit_events WHERE tenant_id = $1 "
        "AND action IN ('legal_hold.placed', 'retention_policy.updated', 'incident.recorded')",
        TENANT,
    )
    by_action: dict[str, set[str]] = {}
    for row in rows:
        assert row["actor_kind"] == "human"
        by_action.setdefault(row["action"], set()).add(row["actor_id"])
    assert by_action == {
        "legal_hold.placed": {
            stable_id("user:victor-hammond"),
            stable_id("user:neil-ashcroft"),
        },
        "retention_policy.updated": {stable_id("user:felix-andersen")},
        "incident.recorded": {stable_id("user:felix-andersen")},
    }
    again = await loader.load(loaded.superuser_dsn, "E0", slices=("compliance",), wait=False)
    assert again.replayed == 0


@pytest.mark.xfail(
    strict=True,
    reason=(
        "TASK-1242: the register (#393, DEC-290) numbers a firm's incidents itself; canon's "
        "earlier 2026 incidents are not seedable yet, so the slice's one incident is the "
        "firm's INC-2026-001"
    ),
)
async def test_the_incident_carries_its_canon_reference(loaded: Database) -> None:
    golden = cast(dict[str, object], _golden()["incident"])
    incident = await _incident(Seeder(loaded.superuser_dsn))
    assert incident["ref"] == golden["canon_ref"]
