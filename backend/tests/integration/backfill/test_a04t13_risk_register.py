"""A-04-T13 (TASK-2901; A-04 §3.4 AC4.1, AC4.2, AC4.5, AC4.6, AC4.7; SPEC-620; DEC-1951).

Row acceptance: "The Northwind tally reads 10 / 2 (+1 proposed) / 2 / 3 / 1 from the grid, a
rebuttal on R1 returns 422 presumption_not_rebuttable, and the coverage check returns 10 of 10
with R8 unaddressed."

Boundary: `create_app()` over HTTP on the migrated test database. The firm's RMM matrix goes in
as a firm imports it (K-02's workbook, then its owner's publish). The ten Northwind risks are the
AUD-08 handoff's grid, typed here: (area, assertions, IR, CR, presumption).
"""

from __future__ import annotations

import uuid
from dataclasses import replace
from typing import Final, cast

import pytest

from abacus.kernel.clock import today
from abacus.kernel.flags import forget_flags
from abacus.modules.methodology.api import (
    create_standard,
    import_standard_workbook,
    publish_standard,
    standard_workbook,
)

from .tb_support import Books, Json, books

pytestmark = pytest.mark.asyncio

FLAGS: Final = ("assurance.risk_register",)
LEVELS: Final = ("low", "moderate", "high")
MATRIX: Final[Json] = {
    "kind": "rmm_matrix",
    "rows": [
        {"inherent_risk": ir, "control_risk": cr, "rmm": rmm}
        for ir, row in {
            "low": ("low", "low", "low", "low"),
            "moderate": ("low", "moderate", "moderate", "moderate"),
            "high": ("moderate", "high", "high", "high"),
        }.items()
        for cr, rmm in zip(("low", "moderate", "high", "max"), row, strict=True)
    ],
}
GRID: Final = (
    ("Management override of controls", [], "high", "management_override"),
    ("Contributions — participant & employer", ["occurrence", "accuracy"], "moderate", "none"),
    (
        "Contributions — remittance & cutoff",
        ["completeness", "cutoff"],
        "high",
        "revenue_recognition",
    ),
    ("Investments at fair value (certified)", ["existence", "valuation"], "low", "none"),
    ("Investment income (certified)", ["occurrence", "accuracy"], "low", "revenue_recognition"),
    ("Notes receivable from participants", ["existence", "valuation"], "moderate", "none"),
    ("Benefit payments", ["occurrence", "accuracy"], "moderate", "none"),
    (
        "Participant accounts — eligibility & deferral data",
        ["completeness", "accuracy"],
        "high",
        "none",
    ),
    ("Administrative expenses", ["occurrence"], "low", "none"),
    ("Disclosures — parties in interest", ["presentation", "completeness"], "moderate", "none"),
)
RESPONSES: Final = {
    "R1": ["Journal entries"],
    "R2": ["EBP-04"],
    "R3": ["EBP-04"],
    "R4": ["EBP-06"],
    "R5": ["EBP-06"],
    "R6": ["EBP-05"],
    "R7": ["EBP-05"],
    "R9": ["EBP-09"],
    "R10": ["Parties in interest", "EBP-04"],
}


@pytest.fixture
async def world(net: object) -> Books:
    found = await books(net)  # pyright: ignore[reportArgumentType] -- the backfill `net` fixture
    for flag in FLAGS:
        await found.seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'test-seed', 'A-04-T13') ON CONFLICT DO NOTHING",
            found.tenant_id,
            flag,
        )
    forget_flags()
    await found.seed.run(
        "UPDATE memberships SET firm_role = 'practice_leader', level = 'partner' "
        "WHERE tenant_id = $1 AND user_id = $2",
        found.tenant_id,
        found.partner.user_id,
    )
    owner = replace(await found.human(found.partner), firm_role="practice_leader")
    standard = await create_standard(
        owner, kind="rmm_matrix", key="bh-rmm-matrix", name="BH matrix", owner_id=owner.user_id
    )
    await import_standard_workbook(
        owner, standard.id, standard_workbook(standard.kind, standard.name, MATRIX)
    )
    await publish_standard(
        owner, standard.id, effective_from=await today(owner.tenant), change_summary="v1"
    )
    return found


def _path(world: Books, rest: str) -> str:
    return f"/v1/engagements/{world.site.engagement_id}/risks{rest}"


def _keyed() -> dict[str, str]:
    return {"Idempotency-Key": str(uuid.uuid4())}


async def _create(world: Books, area: str, assertions: list[str], ir: str, presumed: str) -> Json:
    response = await world.call(
        "POST",
        _path(world, "/register"),
        world.senior,
        {
            "level": "financial_statement" if not assertions else "assertion",
            "area_label": area,
            "assertions": assertions,
            "inherent_risk": ir,
            "control_risk": "max",
            "presumption_kind": presumed,
        },
        headers=_keyed(),
    )
    assert response.status_code == 201, response.text
    return cast(Json, cast(Json, response.json())["risk"])


async def _northwind(world: Books) -> dict[str, Json]:
    made = {}
    for area, assertions, ir, presumed in GRID:
        risk = await _create(world, area, assertions, ir, presumed)
        made[cast(str, risk["code"])] = risk
    return made


async def _patch(world: Books, risk: Json, body: Json) -> tuple[int, Json]:
    response = await world.call(
        "PATCH",
        _path(world, f"/{risk['id']}"),
        world.senior,
        {"expected_version": risk["version_no"]} | body,
        headers=_keyed(),
    )
    return response.status_code, cast(Json, response.json())


async def test_ac4_1_the_tally_is_counted_from_the_grid(world: Books) -> None:
    made = await _northwind(world)
    # Management override is significant by rule; the team proposes R3 and a rebuttal of R5's
    # presumed fraud risk (AUD-08 a).
    assert made["R1"]["significance"] == "mandatory"
    status, _ = await _patch(world, made["R3"], {"significance": "proposed"})
    assert status == 200
    status, _ = await _patch(world, made["R5"], {"fraud": "rebuttal_proposed"})
    assert status == 200
    for code, targets in RESPONSES.items():
        for target in targets:
            kind = "workpaper" if target.startswith("EBP-") else "program_step"
            linked = await world.call(
                "POST",
                _path(world, f"/{made[code]['id']}/responses"),
                world.senior,
                {"target_kind": kind, "target_ref": target},
                headers=_keyed(),
            )
            assert linked.status_code == 201, linked.text
    register = await world.call("GET", _path(world, "/register"), world.staff)
    assert register.status_code == 200, register.text
    body = cast(Json, register.json())
    tally = cast(Json, body["tally"])
    assert (tally["risks"], tally["significant"], tally["significant_proposed"]) == (10, 2, 1)
    assert (tally["fraud"], tally["high_rmm"], tally["unaddressed"]) == (2, 3, 1)
    assert tally["ep_approval"] == "pending"
    assert [r["code"] for r in cast(list[Json], body["risks"]) if r["rmm"] == "high"] == [
        "R1",
        "R3",
        "R8",
    ]
    assert {r["control_risk"] for r in cast(list[Json], body["risks"])} == {"max"}
    assert len(cast(str, body["register_hash"])) == 64
    assert "$" not in register.text


async def test_ac4_2_rmm_is_recomputed_from_the_firm_matrix(world: Books) -> None:
    made = await _northwind(world)
    status, drawer = await _patch(
        world, made["R4"], {"inherent_risk": "high", "control_risk": "low"}
    )
    assert status == 200
    risk = cast(Json, drawer["risk"])
    assert (risk["rmm"], risk["version_no"]) == ("moderate", 2)
    assert risk["rmm_policy_version_id"] is not None


async def test_ac4_5_management_override_is_never_rebuttable(world: Books) -> None:
    made = await _northwind(world)
    status, body = await _patch(world, made["R1"], {"fraud": "rebuttal_proposed"})
    assert (status, body["detail"]) == (422, "presumption_not_rebuttable")


async def test_ac4_7_coverage_names_r8_unaddressed(world: Books) -> None:
    made = await _northwind(world)
    for code, targets in RESPONSES.items():
        for target in targets:
            kind = "workpaper" if target.startswith("EBP-") else "program_step"
            await world.call(
                "POST",
                _path(world, f"/{made[code]['id']}/responses"),
                world.senior,
                {"target_kind": kind, "target_ref": target},
                headers=_keyed(),
            )
    found = await world.call("POST", _path(world, "/coverage"), world.staff)
    assert found.status_code == 200, found.text
    assert found.json()["unaddressed_codes"] == ["R8"]


async def test_staff_may_not_edit_and_versions_conflict(world: Books) -> None:
    made = await _northwind(world)
    refused = await world.call(
        "PATCH",
        _path(world, f"/{made['R2']['id']}"),
        world.staff,
        {"expected_version": 1, "inherent_risk": "high"},
        headers=_keyed(),
    )
    assert refused.status_code == 403
    status, _ = await _patch(world, made["R2"], {"inherent_risk": "high"})
    assert status == 200
    stale, body = await _patch(world, made["R2"], {"inherent_risk": "low"})  # still version 1
    assert (stale, body["detail"]) == (409, "version_conflict")
