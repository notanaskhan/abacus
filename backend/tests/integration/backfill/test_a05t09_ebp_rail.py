"""A-05-T09 (TASK-2906; SPEC-641; DEC-1954): the EBP designed workpapers on the cockpit rail.

Row acceptance (rail half): "Rail rows appear on the Northwind cockpit with canonical statuses."
An EBP audit shows the nine rows in the planning and fieldwork bands with C2 `audit_section`
codes; an FS audit shows none of them (fail closed).
"""

from __future__ import annotations

from typing import Final, cast

import pytest

from abacus.kernel._statuses import AuditSectionStatus
from abacus.kernel.flags import forget_flags

from .tb_support import Books, Json, books

pytestmark = pytest.mark.asyncio

EBP_ROWS: Final = {f"ebp_0{n}" for n in range(1, 10)}


async def _cockpit(world: Books, plan: str | None) -> list[Json]:
    await world.seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'audits.cockpit', 'true', 'test-seed', 'A-05-T09') ON CONFLICT DO NOTHING",
        world.tenant_id,
    )
    forget_flags()
    await world.seed.run_untriggered(
        "INSERT INTO assurance_work_items (work_item_id, tenant_id, engagement_id, "
        "assurance_type, ebp_plan_kind) VALUES ($1, $2, $3, $4, $5) "
        "ON CONFLICT (work_item_id) DO UPDATE SET ebp_plan_kind = $5, assurance_type = $4",
        world.work_item_id,
        world.tenant_id,
        world.site.engagement_id,
        "ebp_audit" if plan else "fs_audit",
        plan,
    )
    found = await world.call("GET", f"/v1/audits/{world.work_item_id}/cockpit", world.manager)
    assert found.status_code == 200, found.text
    return [
        row
        for band in cast(list[Json], found.json()["bands"])
        for row in cast(list[Json], band["rows"])
    ]


async def test_an_ebp_audit_shows_the_nine_rows_with_canonical_statuses(net: object) -> None:
    world = await books(net)  # pyright: ignore[reportArgumentType] -- the backfill `net` fixture
    rows = {cast(str, r["key"]): r for r in await _cockpit(world, "dc")}
    assert set(rows) >= EBP_ROWS
    codes = {s.value for s in AuditSectionStatus}
    for key in EBP_ROWS:
        assert rows[key]["section_state"] in codes
        assert rows[key]["section_state"] == "not_started"
        assert rows[key]["route"] == key.upper().replace("_", "-")
        assert rows[key]["link"] == ("live" if key == "ebp_01" else "planned")


async def test_an_fs_audit_shows_none_of_them(net: object) -> None:
    world = await books(net)  # pyright: ignore[reportArgumentType] -- the backfill `net` fixture
    keys = {r["key"] for r in await _cockpit(world, None)}
    assert not (EBP_ROWS & keys)
