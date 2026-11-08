"""A-06 (TASK-3361; DEC-2360): a person states a misstatement's effect; AUD-16's strips read code.

Real units of work against the migrated tables: stubbed tests would miss a refused `Ref`, a grant
or a target the audit explorer can't place.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import cast

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.assurance import sum_service

from .tb_support import Books, Json, books

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def world(net: object) -> Books:
    found = await books(net)  # pyright: ignore[reportArgumentType] -- the backfill `net` fixture
    # A-06-T37 (DEC-2714): the `assurance_completion` entitlement replaces the retired flag.
    await found.seed.run(
        "INSERT INTO tenant_entitlements (tenant_id, module, valid_from, set_by) "
        "VALUES ($1, 'assurance_completion', '2000-01-01', 'test-seed') ON CONFLICT DO NOTHING",
        found.tenant_id,
    )
    return found


async def _misstatement(world: Books) -> tuple[uuid.UUID, uuid.UUID]:
    work_item = world.work_item_id
    made = cast(
        uuid.UUID,
        await world.seed.value(
            "INSERT INTO audit_misstatements (tenant_id, engagement_id, work_item_id, ref, type, "
            "status, amount, column_set) VALUES ($1, $2, $3, 'M-1', 'judgmental', 'confirmed', "
            "13050, 'ebp_net_assets') RETURNING id",
            world.tenant_id,
            world.site.engagement_id,
            work_item,
        ),
    )
    return work_item, made


async def test_ac_a_person_states_the_effect_and_a_stale_version_is_refused(world: Books) -> None:
    work_item, made = await _misstatement(world)
    body: Json = {
        "seen_version": 1,
        "fs_effect": {
            "description": "Accrued administrative expenses",
            "liabilities": "13050.00",
            "net_assets": "-13050.00",
            "change_in_net_assets": "-1150.00",
        },
    }
    keyed = {"Idempotency-Key": uuid.uuid4().hex}
    first = await world.call(
        "PATCH", f"/v1/misstatements/{made}/effect", world.manager, body, headers=keyed
    )
    assert first.status_code == 200, first.text
    stale = await world.call(
        "PATCH",
        f"/v1/misstatements/{made}/effect",
        world.manager,
        body,
        headers={"Idempotency-Key": uuid.uuid4().hex},
    )
    assert stale.status_code == 409, stale.text
    tenant = TenantContext(world.tenant_id, "system", "test")
    row = await sum_service.misstatement(tenant, work_item, made)
    assert sum_service.effects(row) == (Decimal("-1150.00"), Decimal("-13050.00"))
    assert sum_service.column_total([row], "liabilities") == Decimal("13050.00")
    assert sum_service.column_total([row], "assets") is None


async def test_ac_the_strips_read_not_requested_until_a_snapshot_and_a_card(world: Books) -> None:
    work_item, _made = await _misstatement(world)
    tenant = TenantContext(world.tenant_id, "system", "test")
    before = await sum_service.strips(tenant, work_item)
    assert before.state == "not_requested"
    assert before.partner_label == "Partner — awaiting conclusion"
    assert before.prepared_label is None
    assert before.partner_signed is False
