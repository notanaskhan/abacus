"""SPEC-644 AC-4 (A-07-T04; TASK-3249): the AUD-18 and AUD-19 contract stub. Every operation is
in the OpenAPI document, each route declares exactly one matrix action, every final verb denies
the agent and the system (I-AGENT-NEVER covers `eqr.concur`), and a stub answers 501 only after
the client 404 and the work item's authorisation (A-07 §4.3, §4.4)."""

from __future__ import annotations

import json

import pytest

from abacus.api.export_openapi import document
from abacus.modules.assurance.completion_contract import router
from abacus.modules.identity.authz.matrix import RULES
from abacus.modules.identity.routing import ACTION_KEY

OPERATIONS = {
    ("get", "/v1/audits/{work_item_id}/eqr"): "eqr.read",
    ("post", "/v1/audits/{work_item_id}/eqr/digest:build"): "eqr.build_digest",
    ("post", "/v1/audits/{work_item_id}/eqr/digest/{card_id}/reviewed"): "eqr.mark_reviewed",
    ("patch", "/v1/audits/{work_item_id}/eqr/checklist/{item_key}"): "eqr.checklist_update",
    ("post", "/v1/audits/{work_item_id}/eqr/concur"): "eqr.concur",
    ("post", "/v1/audits/{work_item_id}/eqr/request"): "eqr.request",
    ("get", "/v1/audits/{work_item_id}/completion"): "completion.read",
    # A-07-T32 (DEC-3109): the readiness check runs the code-only capability.
    ("post", "/v1/audits/{work_item_id}/completion/readiness:check"): "completion.check_readiness",
    ("post", "/v1/audits/{work_item_id}/completion/items/{item_key}/not-applicable"): (
        "completion.update"
    ),
    ("post", "/v1/audits/{work_item_id}/completion/items/{item_key}/reopen"): "completion.update",
    ("get", "/v1/audits/{work_item_id}/subsequent-events"): "completion.read",
    ("post", "/v1/audits/{work_item_id}/subsequent-events/procedures"): "subsequent_event.update",
    ("patch", "/v1/audits/{work_item_id}/subsequent-events/procedures/{procedure_id}"): (
        "subsequent_event.update"
    ),
    ("post", "/v1/audits/{work_item_id}/subsequent-events"): "subsequent_event.create",
    ("get", "/v1/audits/{work_item_id}/legal-letters"): "completion.read",
    ("put", "/v1/audits/{work_item_id}/legal-letters"): "legal_letter.update",
    ("post", "/v1/audits/{work_item_id}/legal-letters/request"): "legal_letter.request",
    ("get", "/v1/audits/{work_item_id}/going-concern"): "completion.read",
    ("post", "/v1/audits/{work_item_id}/going-concern/request-decision"): (
        "going_concern.request_decision"
    ),
}
FINAL_VERBS = ("eqr.concur", "eqr.mark_reviewed", "eqr.checklist_update")
CLIENTS = ("client_admin", "client_contributor", "third_party")


def test_ac4_every_aud18_and_aud19_operation_is_in_the_openapi_document() -> None:
    paths = json.loads(document())["paths"]
    for (method, path), _ in OPERATIONS.items():
        assert method in paths[path], (method, path)
        assert "501" in paths[path][method]["responses"], (method, path)


def test_ac4_each_route_declares_exactly_its_one_matrix_action() -> None:
    declared: dict[tuple[str, str], str] = {
        (m.lower(), r.path): r.openapi_extra[ACTION_KEY]  # type: ignore[attr-defined] -- APIRoute carries methods and openapi_extra
        for r in router.routes
        for m in r.methods  # type: ignore[attr-defined] -- APIRoute carries methods and openapi_extra
    }
    assert declared == OPERATIONS


@pytest.mark.parametrize("action", sorted(set(OPERATIONS.values())))
def test_ac4_no_client_principal_holds_an_a07_action(action: str) -> None:
    for role in CLIENTS:
        assert RULES[action].decisions.get(role) == "deny", (action, role)


@pytest.mark.parametrize("action", FINAL_VERBS)
def test_ac4_agent_and_system_never_hold_the_eqr_final_verbs(action: str) -> None:
    rule = RULES[action]
    assert rule.decisions.get("agent") == "deny"
    assert rule.decisions.get("system") == "deny"


def test_ac4_only_an_eqr_may_concur_and_never_the_engagement_team() -> None:
    allowed = {r for r, d in RULES["eqr.concur"].decisions.items() if d == "allow"}
    assert allowed == {"reviewer", "eqr_reviewer"}
