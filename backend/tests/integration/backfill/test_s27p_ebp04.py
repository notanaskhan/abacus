"""EBP-04 a (TASK-3362; DEC-2361): the waterfall reaches the statements, and says when it doesn't."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.assurance import ebp_remittances

from .tb_support import Books, books

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def world(net: object) -> Books:
    return await books(net)  # pyright: ignore[reportArgumentType] -- the backfill `net` fixture


async def test_ac_the_waterfall_ties_to_the_statements_when_there_is_a_figure(
    world: Books,
) -> None:
    for pay_date, deposited in (
        (date(2025, 12, 12), date(2025, 12, 15)),
        (date(2025, 12, 26), date(2026, 1, 9)),
    ):
        await world.seed.run(
            "INSERT INTO ebp_payrolls (tenant_id, engagement_id, work_item_id, pay_date, "
            "deferrals_pretax, match, deposit_date) VALUES ($1, $2, $3, $4, 1000, 500, $5)",
            world.tenant_id,
            world.site.engagement_id,
            world.work_item_id,
            pay_date,
            deposited,
        )
    tenant = TenantContext(world.tenant_id, "system", "test")
    year_end = date(2025, 12, 31)
    none = await ebp_remittances.reconciliation(tenant, world.work_item_id, year_end)
    assert none.total == Decimal(1500)
    assert none.trust_receipts == Decimal(1500)
    assert none.reconciled == Decimal(3000)
    assert none.ties is None
    tied = await ebp_remittances.reconciliation(
        tenant, world.work_item_id, year_end, Decimal(3000)
    )
    assert tied.ties is True
    off = await ebp_remittances.reconciliation(tenant, world.work_item_id, year_end, Decimal(2999))
    assert off.ties is False
