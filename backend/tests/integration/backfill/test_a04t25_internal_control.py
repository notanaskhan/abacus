"""A-04-T25 (TASK-3206; A-04 §3.6 AC6.2-AC6.6; SPEC-620; DEC-2206).

Row acceptance: "Exceptions!D2 resolves to row 2 with two citations, Send to Findings answers 503
until A-06 registers its router and then routes in one unit of work, and no API path sets a
concluded severity."

Boundary: `create_app()` over HTTP on the migrated test database (the A-04 backfill world). The
sheet's rows are recorded through `assurance.api.record_exceptions` (the drafter's mode `ic`
does the same, A-04-T29); the senior proposes, routes and requests evidence.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Final, cast

import pytest

from abacus.kernel.flags import forget_flags
from abacus.modules.assurance import internal_control as ic
from abacus.modules.assurance.api import ExceptionRow, record_exceptions
from abacus.modules.assurance.planning_contract import ControlExceptionOut

from .tb_support import Books, Json, books

pytestmark = pytest.mark.asyncio

FLAGS: Final = ("assurance.internal_control",)


@pytest.fixture
async def world(net: object) -> Books:
    found = await books(net)  # pyright: ignore[reportArgumentType] -- the backfill `net` fixture
    for flag in FLAGS:
        await found.seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'test-seed', 'A-04-T25') ON CONFLICT DO NOTHING",
            found.tenant_id,
            flag,
        )
    forget_flags()
    return found


def _path(world: Books, rest: str = "") -> str:
    return f"/v1/engagements/{world.site.engagement_id}/internal-control{rest}"


def _keyed() -> dict[str, str]:
    return {"Idempotency-Key": str(uuid.uuid4())}


async def _sheet(world: Books) -> uuid.UUID:
    workpaper = uuid.uuid4()
    await world.seed.run(
        "INSERT INTO workpapers (id, tenant_id, engagement_id, work_item_id, code, title, "
        "created_by) VALUES ($1, $2, $3, $4, 'EBP-140', 'Internal control', $5)",
        workpaper,
        world.tenant_id,
        world.site.engagement_id,
        world.work_item_id,
        world.senior.user_id,
    )
    cites = (uuid.uuid4(), uuid.uuid4())
    await record_exceptions(
        await world.human(world.senior),
        world.site.engagement_id,
        workpaper,
        [
            ExceptionRow(
                sheet_row=2,
                matter="Payroll remittance timing",
                description="PayGrid pay date 12/26/2025; Keystone deposit 1/9/2026",
                coso_component="control_activities",
                proposed_severity="significant_deficiency",
                citation_ids=cites,
            ),
            ExceptionRow(
                sheet_row=3,
                matter="Late deposit",
                description="One remittance deposited late",
                coso_component="control_activities",
                misstatement_candidate_amount=Decimal("48600.00"),
            ),
        ],
    )
    return workpaper


async def test_ac6_2_exceptions_d2_resolves_to_row_2_with_two_citations(world: Books) -> None:
    await _sheet(world)
    response = await world.call("GET", _path(world, "/exceptions"), world.senior)
    assert response.status_code == 200, response.text
    items = cast(list[Json], cast(Json, response.json())["items"])
    rows = [ControlExceptionOut.model_validate(r) for r in items]
    d2 = next(r for r in rows if r.sheet_row == 2)
    assert d2.address == "Exceptions!D2"
    assert len(d2.citation_ids) == 2
    assert d2.proposed_severity == "significant_deficiency"
    assert d2.concluded_severity is None
    assert "exception.route" in d2.allowed_actions  # A-06 registers its routes (DEC-2354)


async def test_ac6_3_a_proposal_never_concludes(world: Books) -> None:
    await _sheet(world)
    response = await world.call(
        "PATCH",
        _path(world, "/exceptions/3/proposed-severity"),
        world.senior,
        {"proposed_severity": "deficiency"},
        headers=_keyed(),
    )
    assert response.status_code == 200, response.text
    body = cast(Json, response.json())
    assert body["proposed_severity"] == "deficiency"
    assert body["disposition"] == "proposed"
    assert body["concluded_severity"] is None
    columns = await world.seed.rows(
        "SELECT column_name FROM information_schema.columns WHERE table_name = "
        "'control_exceptions' AND column_name LIKE '%conclu%'"
    )
    assert columns == []


async def test_ac6_4_send_to_findings_is_503_until_a06_registers_then_routes_once(
    world: Books, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _sheet(world)
    monkeypatch.setattr(ic, "_ROUTERS", {})
    refused = await world.call(
        "POST", _path(world, "/exceptions/2/send-to-findings"), world.senior, headers=_keyed()
    )
    assert refused.status_code == 503, refused.text
    assert cast(Json, refused.json())["detail"] == "route_not_available"

    finding = uuid.uuid4()
    seen: list[str] = []

    async def router(_tx: object, request: ic.RouteRequest) -> uuid.UUID:
        seen.append(request.address)
        return finding

    ic.register_exception_route("finding", router)
    routed = await world.call(
        "POST", _path(world, "/exceptions/2/send-to-findings"), world.senior, headers=_keyed()
    )
    assert routed.status_code == 200, routed.text
    assert cast(Json, routed.json()) == {"routed_kind": "finding", "routed_ref": str(finding)}
    assert seen == ["Exceptions!D2"]
    again = await world.call(
        "POST", _path(world, "/exceptions/2/send-to-findings"), world.senior, headers=_keyed()
    )
    assert again.status_code == 409, again.text


async def test_ac6_4_convert_needs_an_amount(
    world: Books, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _sheet(world)

    async def router(_tx: object, _request: ic.RouteRequest) -> uuid.UUID:
        return uuid.uuid4()

    monkeypatch.setattr(ic, "_ROUTERS", {"misstatement": router})
    no_amount = await world.call(
        "POST",
        _path(world, "/exceptions/2/convert-to-misstatement"),
        world.senior,
        headers=_keyed(),
    )
    assert no_amount.status_code == 409, no_amount.text
    assert cast(Json, no_amount.json())["detail"] == "no_amount"
    converted = await world.call(
        "POST",
        _path(world, "/exceptions/3/convert-to-misstatement"),
        world.senior,
        headers=_keyed(),
    )
    assert converted.status_code == 200, converted.text


async def test_ac6_4_request_evidence_drafts_a_request_nothing_sends(world: Books) -> None:
    await _sheet(world)
    response = await world.call(
        "POST", _path(world, "/exceptions/3/request-evidence"), world.senior, headers=_keyed()
    )
    assert response.status_code == 201, response.text
    item = cast(Json, response.json())["draft_id"]
    sent = await world.seed.value(
        "SELECT sent_at FROM request_items WHERE id = $1", uuid.UUID(cast(str, item))
    )
    assert sent is None


async def test_ac6_6_a_process_records_design_and_a_walkthrough(world: Books) -> None:
    created = await ic.add_process(
        await world.human(world.senior), world.site.engagement_id, "Payroll", None
    )
    response = await world.call(
        "PUT",
        _path(world, f"/processes/{created.id}"),
        world.senior,
        {
            "expected_version": created.row_version,
            "design": "effective",
            "implementation": "implemented",
            "walkthrough_on": "2026-09-08",
        },
        headers=_keyed(),
    )
    assert response.status_code == 200, response.text
    body = cast(Json, response.json())
    assert body["design"] == "effective"
    assert body["walkthrough_on"] == "2026-09-08"
    stale = await world.call(
        "PUT",
        _path(world, f"/processes/{created.id}"),
        world.senior,
        {"expected_version": created.row_version, "design": "deficient"},
        headers=_keyed(),
    )
    assert stale.status_code == 409, stale.text
