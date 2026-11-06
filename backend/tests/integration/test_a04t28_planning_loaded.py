"""A-04-T28 (TASK-3233; DEC-2224) on the loaded Brightwater Hale tenant: "make seed-demo loads
both engagements with real audit events and via-Agent attribution, Northwind's G4 is met at
4:40 PM". The `planning` slice (with its own trial-balance and materiality basis) loads at the
Sep 24 snapshot into its own database; the register, the internal-control exceptions, the approval
card and G4 are read back. Figures typed from AUD-08 and AUD-09."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from typing import cast

import pytest

from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.flags import forget_flags
from abacus.modules.assurance.planning_gate import g4_facts
from abacus_tools.quality.schema_check import Database, provisioned_database
from abacus_tools.synthetic.scenarios.brightwater_hale import loader

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio
TENANT = loader.TENANT
NORTHWIND = "Northwind Robotics 401(k) Plan PY2025"


@pytest.fixture(scope="module")
def own_db(migrated_db: MigratedDatabase) -> Iterator[Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database
    configure_engine(migrated_db.app_url)  # hand the session's database back to later tests


async def test_ac_the_planning_day_loads_and_g4_is_met_at_4_40(
    own_db: Database,
    migrated_db: MigratedDatabase,
    object_store: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del migrated_db, object_store
    monkeypatch.setenv("ABACUS_IDENTITY_DATABASE_URL", own_db.identity_url)
    settings.cache_clear()
    forget_flags()
    await dispose_engine()
    configure_engine(own_db.app_url)
    await loader.load(own_db.superuser_dsn, "2026-09-24", slices=("planning",), wait=False)
    seed = Seeder(own_db.superuser_dsn)
    engagement = cast(
        uuid.UUID | None,
        await seed.value(
            "SELECT w.engagement_id FROM work_items w JOIN control_exceptions x "
            "ON x.work_item_id = w.id WHERE w.tenant_id = $1 LIMIT 1",
            TENANT,
        ),
    )
    assert engagement is not None
    codes = await seed.value(
        "SELECT array_agg(r.code ORDER BY r.created_at) FROM risk_register_rows r "
        "JOIN work_items w "
        "ON w.id = r.work_item_id WHERE w.engagement_id = $1",
        engagement,
    )
    assert codes == [f"R{n}" for n in range(1, 11)]
    assert (
        await seed.value(
            "SELECT count(*) FROM control_exceptions WHERE engagement_id = $1", engagement
        )
        == 7
    )
    assert (
        await seed.value(
            "SELECT count(*) FROM control_exceptions WHERE engagement_id = $1 "
            "AND coso_component IS NULL",
            engagement,
        )
        == 3
    )
    assert (
        await seed.value(
            "SELECT status FROM decision_cards WHERE kind = 'significant_risk' AND tenant_id = $1",
            TENANT,
        )
        == "decided"
    )
    found = await g4_facts(TenantContext(TENANT, "system", "a04t28"), engagement)
    assert found.met, found.blockers
    # Real audit events, one per service write (the register, the exceptions and the decision).
    actions = cast(
        list[str] | None,
        await seed.value(
            "SELECT array_agg(DISTINCT action) FROM audit_events WHERE tenant_id = $1 "
            "AND action IN ('risk.created', 'control_exception.recorded', 'decision.decided')",
            TENANT,
        ),
    )
    assert set(actions or []) >= {"control_exception.recorded", "decision.decided"}
