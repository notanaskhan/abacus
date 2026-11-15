# ac-test-author: ayushkbhatia
"""A-09-T06 (TASK-8056; SPEC-658 AC-0.5, AC-5.1 to AC-5.3, AC-7.1; DEC-5041): consumer tests for
the group-audit stub and the component room. One action per operation with 404 and 501; the room
is the component auditor's alone (`client_contributor` with `scope_only`); no firm write reaches a
portal principal or the agent; and materiality, PMs and coverage foot.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import cast

import pytest
from pydantic import BaseModel

from abacus.api.export_openapi import document
from abacus.kernel.classification import unclassified_fields
from abacus.modules.assurance import group_fixtures as fx
from abacus.modules.identity.authz import _matrix
from abacus.modules.portal import component_room_contract as rc

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
A = "/v1/audits/{work_item_id}"
R = "/v1/portal/component-rooms/{room_id}"
ROUTES: dict[tuple[str, str], str] = {
    ("get", f"{A}/group-scoping"): "group_scoping.read",
    ("get", f"{A}/group-scoping/export.xlsx"): "group_scoping.read",
    ("put", "/v1/components/{component_id}"): "component.edit",
    ("post", f"{A}/decisions/group-materiality"): "group_materiality.propose",
    ("get", f"{A}/component-auditors"): "component_auditor.read",
    ("post", f"{A}/component-auditors"): "component_auditor.manage",
    (
        "post",
        "/v1/component-auditors/{auditor_id}/instructions/draft",
    ): "component_instructions.draft",
    ("patch", "/v1/component-instructions/{instructions_id}"): "component_instructions.edit",
    ("post", "/v1/component-instructions/{instructions_id}/send"): "component_instructions.send",
    ("post", "/v1/component-auditors/{auditor_id}/make-reference"): "component_auditor.manage",
    ("get", "/v1/component-auditors/{auditor_id}/deliverables"): "component_deliverable.read",
    ("post", "/v1/component-auditors/{auditor_id}/deliverables"): "component_deliverable.manage",
    ("post", "/v1/component-deliverables/{deliverable_id}/review"): "component_deliverable.review",
    ("post", "/v1/component-deliverables/{deliverable_id}/return"): "component_deliverable.review",
    ("get", R): "component_room.read",
    ("get", f"{R}/instructions"): "component_room.read",
    ("get", f"{R}/instructions/pdf"): "component_room.read",
    ("post", f"{R}/instructions/acknowledge"): "component_instructions.acknowledge",
    ("post", f"{R}/deliverables/{{deliverable_id}}/uploads"): "component_deliverable.upload",
    ("post", f"{R}/drops"): "component_deliverable.upload",
    ("get", f"{R}/questions"): "component_room.read",
    ("post", f"{R}/questions"): "component_room.ask",
}
ROOM = {
    "component_room.read",
    "component_instructions.acknowledge",
    "component_deliverable.upload",
    "component_room.ask",
}
PORTAL = ("client_admin", "client_contributor", "third_party", "client_service", "link_principal")


@pytest.mark.parametrize(("method", "path"), sorted(ROUTES))
def test_each_route_declares_its_action_and_404_and_501(method: str, path: str) -> None:
    operation = PATHS[path][method]
    assert operation["x-abacus-action"] == ROUTES[(method, path)]
    assert {"404", "501"} <= set(cast(Json, operation["responses"]))


def test_the_room_models_are_classified() -> None:
    models = [
        v
        for v in vars(rc).values()
        if isinstance(v, type) and issubclass(v, BaseModel) and v.__module__ == rc.__name__
    ]
    assert models
    for model in models:
        assert unclassified_fields(model) == [], model.__name__


def test_ac7_1_the_room_is_the_component_auditors_alone() -> None:
    for action in ROOM:
        cells = _matrix.ACTIONS[action]
        allowed = {r for r, d in cells.items() if d not in ("deny", "required")}
        assert allowed == {"client_contributor"}, action
        assert cells.get("scope_only") == "required", action


def test_no_firm_group_write_reaches_a_portal_principal_or_the_agent() -> None:
    firm = (
        set(ROUTES.values())
        - ROOM
        - {"component_auditor.read", "component_deliverable.read", "group_scoping.read"}
    )
    for action in firm:
        cells = _matrix.ACTIONS[action]
        assert all(cells.get(r, "deny") == "deny" for r in PORTAL), action
        if action != "component_instructions.draft":
            assert cells.get("agent", "deny") == "deny", action


def test_ac5_1_group_materiality_240_000_180_000_12_000() -> None:
    assert fx.group_materiality() == (Decimal(240_000), Decimal(180_000), Decimal(12_000))


def test_ac5_2_component_pms_below_group_pm_sum_384_000() -> None:
    _overall, pm, _ct = fx.group_materiality()
    assert sum(fx.COMPONENT_PMS.values()) == Decimal(384_000)
    assert all(v < pm for v in fx.COMPONENT_PMS.values())
    assert "operating" not in fx.COMPONENT_PMS  # Operating Co. has none


def test_ac5_3_coverage_is_78_and_22_percent_of_50_760_000() -> None:
    full, specific, total = fx.coverage()
    assert (full, specific, total) == (
        Decimal(39_760_000),
        Decimal(11_000_000),
        Decimal(50_760_000),
    )
    assert full + specific == total
    assert round(full * 100 / total) == 78
