"""F-03-T28 against Postgres (migration 0088): a firm's entitlement is its row, enabled and in
date; another firm's row is never read; the app writes none."""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest

from abacus.kernel.clock import today as clock_today
from abacus.kernel.db import TenantContext, configure_engine
from abacus.modules.platform.api import EntitlementRequired, check_entitlement, entitlement

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio


@pytest.fixture
def seed(migrated_db: MigratedDatabase) -> Seeder:
    configure_engine(migrated_db.app_url)  # a fresh pool on this test's event loop
    return Seeder(migrated_db.superuser_dsn)


async def _firm(seed: Seeder) -> TenantContext:
    tenant = uuid.uuid4()
    await seed.run("INSERT INTO firms (tenant_id, name) VALUES ($1, 'Probe')", tenant)
    return TenantContext(tenant, "human", "probe")


_GRANT = (
    "INSERT INTO tenant_entitlements (tenant_id, module, enabled, seats, "
    "agent_minutes_allowance, valid_from, valid_to, set_by) "
    "VALUES ($1, $2, $3, 46, 1000, $4, $5, 'operator:probe')"
)


async def test_an_enabled_in_date_row_is_the_entitlement(seed: Seeder) -> None:
    firm, other = await _firm(seed), await _firm(seed)
    today = await clock_today(firm)  # the business date the check uses (Central), not the host's
    await seed.run(_GRANT, firm.tenant_id, "attest", True, today - timedelta(days=1), None)
    await seed.run(_GRANT, other.tenant_id, "insights", True, today, None)
    held = await entitlement(firm, "attest")
    assert held is not None and (held.seats, held.agent_minutes_allowance) == (46, 1000)
    assert await entitlement(firm, "insights") is None  # the other firm's row
    with pytest.raises(EntitlementRequired):
        await check_entitlement(firm, "insights")


async def test_switched_off_or_lapsed_is_no_entitlement(seed: Seeder) -> None:
    firm = await _firm(seed)
    today = await clock_today(firm)  # the business date the check uses (Central), not the host's
    await seed.run(_GRANT, firm.tenant_id, "attest", False, today, None)
    await seed.run(
        _GRANT,
        firm.tenant_id,
        "group_audit",
        True,
        today - timedelta(days=30),
        today - timedelta(days=1),
    )
    assert await entitlement(firm, "attest") is None
    assert await entitlement(firm, "group_audit") is None


async def test_the_app_cannot_write_entitlements_or_plans(seed: Seeder) -> None:
    for table in ("tenant_entitlements", "plans"):
        for privilege in ("INSERT", "UPDATE", "DELETE"):
            granted = await seed.value(
                "SELECT has_table_privilege('abacus_app', $1, $2)", table, privilege
            )
            assert granted is False, (table, privilege)
