"""A-05-T10 (TASK-2907; A-05 §3 F1; SPEC-640; DEC-1955): the EBP-01 service over HTTP.

Row acceptance: "Northwind reads large filer, due Oct 15, 2026, one SOC gap on Keystone and one
EIN mismatch routed to Summit; PN 58217 or 000 is refused with the Form 5500 helper, and a staff
member's PATCH answers 403." Figures typed from the A-05 plan and the EBP golden.
"""

from __future__ import annotations

import uuid
from typing import Final, cast

import pytest

from abacus.kernel.flags import forget_flags

from .tb_support import Books, Json, books

pytestmark = pytest.mark.asyncio

NOTE: Final = "Adoption agreement v2 and the recordkeeper's plan summary"


@pytest.fixture
async def world(net: object) -> Books:
    found = await books(net)  # pyright: ignore[reportArgumentType] -- the backfill `net` fixture
    await found.seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'ebp.modules', 'true', 'test-seed', 'A-05-T10') ON CONFLICT DO NOTHING",
        found.tenant_id,
    )
    forget_flags()
    await found.seed.run_untriggered(
        "INSERT INTO assurance_work_items (work_item_id, tenant_id, engagement_id, "
        "assurance_type, ebp_plan_kind, limited_scope_103a3c) "
        "VALUES ($1, $2, $3, 'ebp_audit', 'dc', true) "
        "ON CONFLICT (work_item_id) DO UPDATE "
        "SET ebp_plan_kind = 'dc', limited_scope_103a3c = true",
        found.work_item_id,
        found.tenant_id,
        found.site.engagement_id,
    )
    return found


def _path(world: Books, rest: str) -> str:
    return f"/v1/audits/{world.work_item_id}/ebp{rest}"


def _keyed() -> dict[str, str]:
    return {"Idempotency-Key": str(uuid.uuid4())}


async def _patch(world: Books, fields: dict[str, str], seen: int = 1, who: object = None) -> Json:
    response = await world.call(
        "PATCH",
        _path(world, "/plan"),
        who or world.senior,  # type: ignore[arg-type]
        {"fields": fields, "citation_note": NOTE, "seen_version": seen},
        headers=_keyed(),
    )
    return {"status": response.status_code, **cast(Json, response.json())}


async def _northwind(world: Books) -> None:
    found = await _patch(
        world,
        {
            "plan_year_start": "2025-01-01",
            "plan_year_end": "2025-12-31",
            "safe_harbor": "qaca",
            "recordkeeper_plan_id": "58217",
            "participants_boy_with_balances": "286",
            "participants_eoy": "301",
            "prior_year_filer": "large_plan",
            "form_5558_filed_on": "2026-07-20",
        },
    )
    assert found["status"] == 200, found


async def test_northwind_reads_large_filer_due_oct_15_2026(world: Books) -> None:
    await _northwind(world)
    plan = cast(Json, (await world.call("GET", _path(world, "/plan"), world.staff)).json())
    assert (plan["filer_status"], plan["form5500_due_on"]) == ("large_plan", "2026-10-15")
    assert (plan["participants_boy"], plan["participants_eoy"]) == (286, 301)
    assert plan["audit_kind"] == "103a3c"


@pytest.mark.parametrize(("pn", "reason"), [("58217", "recordkeeper_id"), ("000", "zero")])
async def test_a_plan_number_is_refused_with_the_form_5500_helper(
    world: Books, pn: str, reason: str
) -> None:
    await _northwind(world)
    found = await _patch(world, {"plan_number": pn}, seen=1)
    assert (found["status"], found["detail"]) == (422, "plan_number_invalid")
    assert found["facts"] == {"reason": reason, "helper": "form_5500_line_1b"}


async def test_a_staff_members_patch_is_403(world: Books) -> None:
    await _northwind(world)
    found = await _patch(world, {"qdia": "Target date funds"}, seen=1, who=world.staff)
    assert found["status"] == 403


async def test_one_soc_gap_on_keystone_and_one_ein_mismatch_routed_to_summit(
    world: Books,
) -> None:
    await _northwind(world)
    summit = await world.call(
        "POST",
        _path(world, "/providers"),
        world.senior,
        {"name": "Summit Plan Administrators", "role": "tpa"},
        headers=_keyed(),
    )
    assert summit.status_code == 201, summit.text
    keystone = await world.call(
        "POST",
        _path(world, "/providers"),
        world.senior,
        {
            "name": "Keystone Retirement Svcs LLC",
            "role": "recordkeeper",
            "soc_type": "soc1_type2",
            "soc_period_start": "2025-01-01",
            "soc_period_end": "2025-09-30",
            "agreement_ein_last4": "4420",
            "schedule_c_ein_last4": "4402",
        },
        headers=_keyed(),
    )
    assert keystone.status_code == 201, keystone.text
    flagged = await world.seed.value(
        "SELECT string_agg(check_kind, ',' ORDER BY check_kind) FROM ebp_provider_checks "
        "WHERE work_item_id = $1 AND result = 'flag'",
        world.work_item_id,
    )
    assert flagged == "ein_mismatch,soc_gap"
    routed = await world.seed.value(
        "SELECT facts->>'routed_to_provider_id' FROM ebp_provider_checks "
        "WHERE work_item_id = $1 AND check_kind = 'ein_mismatch'",
        world.work_item_id,
    )
    assert routed == summit.json()["id"]
    listed = cast(Json, (await world.call("GET", _path(world, "/providers"), world.staff)).json())
    row = next(p for p in cast(list[Json], listed["items"]) if p["name"].startswith("Keystone"))  # type: ignore[union-attr]
    assert row["status"] == "correction_requested"
    assert row["soc_report"] == "SOC 1 Type 2, Jan 1 to Sep 30, 2025"
    assert "4402" in cast(str, row["check_note"]) and "Summit" in cast(str, row["check_note"])
