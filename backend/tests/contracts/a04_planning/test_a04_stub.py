"""The A-04 contract stubs (A-04-T01; docs/contracts/workpapers-core.md, audit-planning.md).

Every A-04 §4.3 route the stub owns exists with its one matrix action and documents 404 and 501;
nothing is stubbed over a live SPEC-300 or SPEC-308 route; the gate answers clients 404,
authorises before reading the flag, answers 404 with the flag off and 501 with it on; every model
field is classified; the matrix denies the agent every write and every client principal
everything; the six flags default off; the examples foot to 252,200 / 189,150 / 12,610.
"""

from __future__ import annotations

import json
import uuid
from decimal import ROUND_HALF_UP, Decimal
from types import SimpleNamespace
from typing import cast

import pytest
from pydantic import BaseModel

from abacus.api.export_openapi import document
from abacus.kernel import _flags
from abacus.kernel.classification import unclassified_fields
from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.modules.assurance import planning_contract as planning
from abacus.modules.identity.api import AuthContext
from abacus.modules.identity.authz import _matrix
from abacus.modules.workpapers import contract as core

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
E = "/v1/engagements/{engagement_id}"
WP = f"{E}/workpapers/{{workpaper_id}}"
SOC = f"{E}/soc-reports/{{soc_report_id}}"
EX = f"{E}/internal-control/exceptions/{{sheet_row}}"
# A-04-T04 (DEC-1762), T07 (DEC-1867) and T11 (DEC-1868) serve these: their action and 404 stay,
# 501 goes.
SERVED: dict[tuple[str, str], str] = {
    ("post", f"{WP}/drafts"): "workpaper.draft",
    ("get", f"{E}/program-tailoring"): "procedure.read",
    ("patch", f"{E}/procedures/{{procedure_id}}"): "procedure.tailor",
    ("get", f"{E}/service-organizations"): "service_org.read",
    ("post", f"{E}/service-organizations"): "service_org.edit",
    ("get", f"{E}/service-organizations/{{service_org_id}}"): "service_org.read",
    ("patch", f"{E}/service-organizations/{{service_org_id}}"): "service_org.edit",
    ("get", f"{E}/workpaper-states"): "workpaper.read",
    ("get", f"{WP}/record"): "workpaper.read",
    ("get", f"{WP}/versions"): "workpaper.read",
    ("patch", f"{WP}/cells"): "workpaper.edit",
    ("get", f"{WP}/export.xlsx"): "workpaper.export",
}
ROUTES: dict[tuple[str, str], str] = {
    ("post", f"{WP}/flags/{{flag_id}}/convert"): "attention_flag.convert",
    ("post", f"{WP}/flags/{{flag_id}}/remind"): "follow_up.draft",
    ("get", f"{E}/materiality/current"): "materiality.read",
    ("post", f"{E}/materiality/preview"): "materiality.read",
    ("post", f"{E}/materiality/proposals"): "materiality.propose",
    ("post", f"{E}/materiality/reassessments"): "materiality.reassess",
    ("get", f"{E}/risks/register"): "risk.read",
    ("get", f"{E}/risks/linkage"): "risk.read",
    ("post", f"{E}/risks/approval-requests"): "risk.route_for_approval",
    ("post", f"{E}/risks/coverage"): "risk.read",
    ("get", f"{E}/risks/{{risk_id}}"): "risk.read",
    ("patch", f"{E}/risks/{{risk_id}}"): "risk.edit",
    ("post", f"{E}/risks/{{risk_id}}/responses"): "risk.link",
    ("delete", f"{E}/risks/{{risk_id}}/responses"): "risk.link",
    ("post", f"{E}/risks/{{risk_id}}/drafts"): "workpaper.draft",
    ("get", f"{E}/fraud-brainstorm"): "fraud_session.read",
    ("put", f"{E}/fraud-brainstorm"): "fraud_session.edit",
    ("put", f"{E}/fraud-brainstorm/minutes"): "fraud_session.edit",
    ("post", f"{E}/fraud-brainstorm/minutes/approve"): "fraud_minutes.approve",
    ("get", f"{E}/fraud-inquiries"): "fraud_session.read",
    ("post", f"{E}/fraud-inquiries"): "fraud_inquiry.request",
    ("get", f"{E}/internal-control/processes"): "control.read",
    ("get", f"{E}/internal-control/processes/{{process_id}}"): "control.read",
    ("put", f"{E}/internal-control/processes/{{process_id}}"): "control.edit",
    ("get", f"{E}/internal-control/exceptions"): "control.read",
    ("patch", f"{EX}/proposed-severity"): "deficiency.propose_severity",
    ("post", f"{EX}/send-to-findings"): "exception.route",
    ("post", f"{EX}/convert-to-misstatement"): "exception.route",
    ("post", f"{EX}/request-evidence"): "request_item.create",
    ("get", SOC): "service_org.read",
    ("patch", SOC): "soc_report.evaluate",
    ("patch", f"{SOC}/cuecs/{{n}}"): "soc_report.evaluate",
    ("post", f"{SOC}/drafts"): "workpaper.draft",
    ("post", f"{SOC}/requests"): "request_item.create",
    ("post", f"{SOC}/reliance-requests"): "soc_report.evaluate",
}
# The live SPEC-300 and SPEC-308 operations A-04 must not stub over (DEC-1757).
LIVE = {
    ("get", f"{E}/workpapers"): "workpaper.read",
    ("get", f"{E}/workpapers/{{workpaper_id}}"): "workpaper.read",
    ("put", f"{WP}/cells"): "workpaper.edit",
    ("get", f"{E}/materiality"): "procedure.read",
    ("put", f"{E}/materiality"): "materiality.set",
    ("get", f"{E}/procedures"): "procedure.read",
    ("get", f"{E}/procedures/{{procedure_id}}"): "procedure.read",
    ("get", f"{E}/risks"): "procedure.read",
    ("post", f"{E}/risks"): "risk.assess",
}
A04_ACTIONS = {
    "workpaper.draft", "workpaper.export", "attention_flag.convert", "procedure.tailor",
    "materiality.read", "materiality.propose", "materiality.reassess", "risk.read", "risk.edit",
    "risk.link", "risk.route_for_approval", "fraud_session.read", "fraud_session.edit",
    "fraud_minutes.approve", "fraud_inquiry.request", "control.read", "control.edit",
    "deficiency.propose_severity", "exception.route", "service_org.read", "service_org.edit",
    "soc_report.evaluate",
}  # fmt: skip
READS = {"materiality.read", "risk.read", "fraud_session.read", "control.read", "service_org.read"}
CLIENT_ROLES = ("client_admin", "client_contributor", "third_party", "client_service")
FLAGS = {
    "workpapers.core", "workpapers.drafting", "assurance.materiality", "assurance.risk_register",
    "assurance.internal_control", "assurance.service_orgs",
}  # fmt: skip


def _ctx(*, client: bool = False, kind: str = "human") -> AuthContext:
    user = uuid.uuid4()
    return AuthContext(
        TenantContext(uuid.uuid4(), kind, str(user)),  # type: ignore[arg-type] -- an agent or human probe
        user,
        uuid.uuid4(),
        None,
        None,
        client=client,
    )


@pytest.mark.parametrize(("method", "path"), sorted(ROUTES))
def test_t01_each_route_declares_its_one_action_and_documents_404_and_501(
    method: str, path: str
) -> None:
    operation = PATHS[path][method]
    assert operation["x-abacus-action"] == ROUTES[(method, path)]
    responses = set(cast(Json, operation["responses"]))
    assert {"404", "501"} <= responses


@pytest.mark.parametrize(("method", "path"), sorted(SERVED))
def test_t04_the_served_routes_keep_their_action_and_404_and_answer_no_501(
    method: str, path: str
) -> None:
    operation = PATHS[path][method]
    assert operation["x-abacus-action"] == SERVED[(method, path)]
    responses = set(cast(Json, operation["responses"]))
    assert "404" in responses and "501" not in responses


@pytest.mark.parametrize(("method", "path"), sorted(LIVE))
def test_t01_the_live_routes_keep_their_action_and_answer_no_501(method: str, path: str) -> None:
    operation = PATHS[path][method]
    assert operation["x-abacus-action"] == LIVE[(method, path)]
    assert "501" not in cast(Json, operation["responses"])


def test_t01_every_write_takes_an_idempotency_key() -> None:
    for (method, path), _action in (ROUTES | SERVED).items():
        if method == "get" or path.endswith(("/preview", "/coverage")) or method == "delete":
            continue
        names = {p["name"] for p in cast(list[Json], PATHS[path][method].get("parameters", []))}
        assert "Idempotency-Key" in names, (method, path)


def test_t01_every_field_is_classified() -> None:
    for module in (core, planning):
        models = [
            v
            for v in vars(module).values()
            if isinstance(v, type) and issubclass(v, BaseModel) and v.__module__ == module.__name__
        ]
        assert models
        for model in models:
            assert unclassified_fields(model) == [], model.__name__


@pytest.mark.parametrize("action", sorted(A04_ACTIONS))
def test_t01_clients_hold_nothing_and_the_agent_only_reads(action: str) -> None:
    cells = _matrix.ACTIONS[action]
    for role in CLIENT_ROLES:
        assert cells.get(role) == "deny", (action, role)
    assert cells.get("system") == "deny", action
    assert cells.get("agent") == ("task_scope" if action in READS else "deny"), action


def test_t01_only_the_engagement_partner_approves_the_minutes() -> None:
    allowed = {r for r, v in _matrix.ACTIONS["fraud_minutes.approve"].items() if v == "allow"}
    assert allowed == {"engagement_partner"}


def test_t01_the_six_flags_exist_and_default_off() -> None:
    for name in FLAGS:
        flag = _flags.FLAGS[name]
        assert flag.kind == "boolean"
        assert str(flag.default).lower() == "false", name  # the registry stores the word


def test_t01_the_materiality_examples_foot() -> None:
    """16,812,400 x 1.5% = 252,186 -> 252,200 (nearest 100, half up); PM 75%; CT 5% (AC3.1)."""
    example = cast(Json, planning.ThresholdsOut.model_config.get("json_schema_extra"))
    thresholds = planning.ThresholdsOut.model_validate(cast(list[Json], example["examples"])[0])
    raw = thresholds.benchmark_amount * thresholds.rate_pct / 100
    overall = (raw / 100).quantize(Decimal(1), rounding=ROUND_HALF_UP) * 100
    assert raw == Decimal("252186")
    assert thresholds.overall == overall == Decimal(252_200)
    assert thresholds.pm == overall * thresholds.pm_pct / 100 == Decimal(189_150)
    assert thresholds.ct == overall * thresholds.ct_pct / 100 == Decimal(12_610)
    reassessment = planning.ReassessmentOut.model_validate(
        cast(
            list[Json],
            cast(Json, planning.ReassessmentOut.model_config.get("json_schema_extra"))["examples"],
        )[0]
    )
    at_rate = (reassessment.final_amount * Decimal("0.015") / 100).quantize(
        Decimal(1), rounding=ROUND_HALF_UP
    ) * 100
    assert reassessment.at_rate == at_rate == Decimal(252_900)
    assert reassessment.difference == at_rate - overall == Decimal(700)


async def test_t01_a_client_principal_gets_404_before_anything_else() -> None:
    with pytest.raises(NotFound):
        await core.gate(_ctx(client=True), uuid.uuid4(), "workpaper.read", _flags.WORKPAPERS_CORE)
    with pytest.raises(NotFound):
        await planning.materiality_current_route(uuid.uuid4(), _ctx(client=True))


async def test_t01_the_gate_authorises_then_reads_the_flag_then_answers_501(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    state = {"on": False}

    async def get_ref(_ctx: AuthContext, _eid: uuid.UUID) -> object:
        return SimpleNamespace(resource=lambda: "engagement")

    async def authorise(_ctx: AuthContext, action: str, resource: object) -> None:
        calls.append(f"authorise:{action}:{resource}")

    async def flag(_tenant: object, f: object) -> bool:
        calls.append(f"flag:{getattr(f, 'name', f)}")
        return state["on"]

    for module in (core, planning):
        monkeypatch.setattr(module, "get_ref", get_ref)
        monkeypatch.setattr(module, "authorise", authorise)
        monkeypatch.setattr(module, "flag_enabled", flag)
    with pytest.raises(NotFound):
        await planning.materiality_preview_route(
            uuid.uuid4(),
            planning.MaterialityPreviewIn(
                benchmark_key="net_assets",
                rate_pct=Decimal("1.5"),
                pm_pct=Decimal(75),
                ct_pct=Decimal(5),
            ),
            _ctx(),
        )
    assert calls == ["authorise:materiality.read:engagement", "flag:assurance.materiality"]
    state["on"] = True
    calls.clear()
    from abacus.modules.workpapers import drafting

    run = uuid.uuid4()

    async def started(*_: object) -> uuid.UUID:
        return run

    monkeypatch.setattr(drafting, "start_section_draft", started)
    out = await core.workpaper_draft_route(
        uuid.uuid4(), uuid.uuid4(), core.WorkpaperDraftIn(mode="gap"), _ctx(), "k-1"
    )
    assert out.run_id == run  # A-04-T11 serves the draft route
    assert calls[-2:] == ["flag:workpapers.core", "flag:workpapers.drafting"]
    with pytest.raises(NotImplementedYet):
        await core.attention_flag_convert_route(
            uuid.uuid4(),
            uuid.uuid4(),
            uuid.uuid4(),
            core.FlagConvertIn(to="review_note"),
            _ctx(),
            "k-2",
        )


async def test_t01_the_inventory_answers_with_either_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    async def get_ref(_ctx: AuthContext, _eid: uuid.UUID) -> object:
        return SimpleNamespace(resource=lambda: "engagement")

    async def allow(*_: object) -> None:
        return None

    async def only_core(_tenant: object, f: object) -> bool:
        return getattr(f, "name", "") == "workpapers.core"

    monkeypatch.setattr(planning, "get_ref", get_ref)
    monkeypatch.setattr(planning, "authorise", allow)
    monkeypatch.setattr(planning, "flag_enabled", only_core)
    from abacus.modules.assurance import service_orgs

    async def none_yet(*_: object) -> list[object]:
        return []

    monkeypatch.setattr(planning, "_org_actions", none_yet)
    monkeypatch.setattr(service_orgs, "organizations", none_yet)
    page = await planning.service_orgs_route(uuid.uuid4(), _ctx())
    assert page.total == 0
    with pytest.raises(NotFound):
        await planning.soc_report_route(uuid.uuid4(), uuid.uuid4(), _ctx())
