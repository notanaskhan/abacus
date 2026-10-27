"""C3 v1 consumer tests (P-04-T09), the stubs as a whole: every stub-1 and stub-2 route declares
its one matrix action and answers 404 with `review.grammar_api` off and 501 with it on; every
resolution, decision and sign-off action denies the agent and system principals; the status enums
are the registry's stored codes; and the three review migrations (0093 to 0095) agree with the
wire. `docs/contracts/review-grammar.md` §2, §4, §5 and §6."""

from __future__ import annotations

import inspect
import uuid
from collections.abc import Awaitable, Callable
from types import ModuleType
from typing import cast, get_args

import pytest
from fastapi.routing import APIRoute
from pydantic import BaseModel

from abacus.kernel._flags import REVIEW_GRAMMAR_API
from abacus.kernel.classification import unclassified_fields
from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.modules.agents import contract as agents_contract
from abacus.modules.identity.api import AuthContext
from abacus.modules.identity.authz.matrix import RULES
from abacus.modules.review import contract as review_contract

from ._c3 import PATHS, SCHEMAS, Json, check_list, migration, schema_ref, stored_codes

# (method, path) -> the one matrix action (contract §2, parts 1 and 2).
ROUTES: dict[tuple[str, str], str] = {
    ("get", "/v1/sign-offs"): "sign_off.read",
    ("get", "/v1/sign-offs/eligibility"): "sign_off.read",
    ("post", "/v1/sign-offs"): "sign_off.create",
    ("post", "/v1/sign-offs:bulk"): "sign_off.bulk",
    ("get", "/v1/review-notes"): "review_note.read",
    ("get", "/v1/review-notes/{note_id}"): "review_note.read",
    ("post", "/v1/review-notes"): "review_note.raise",
    ("post", "/v1/review-notes/{note_id}/respond"): "review_note.respond",
    ("post", "/v1/review-notes/{note_id}/clear"): "review_note.clear",
    ("post", "/v1/review-notes/{note_id}/withdraw"): "review_note.withdraw",
    ("get", "/v1/human-gates"): "human_gate.read",
    ("get", "/v1/decision-cards"): "decision.read",
    ("get", "/v1/decision-cards/{card_id}"): "decision.read",
    ("post", "/v1/decision-cards/{card_id}/decide"): "decision.decide",
    ("post", "/v1/decision-cards/{card_id}/analysis-requests"): "decision.request_analysis",
    ("post", "/v1/decision-cards/{card_id}/notify"): "decision.notify",
    ("post", "/v1/decision-cards/{card_id}/reassess"): "decision.reassess",
    ("get", "/v1/proposals/{ref}"): "proposal.read",
    ("post", "/v1/proposals/{proposal_id}/approve"): "proposal.approve",
    ("post", "/v1/proposals/{proposal_id}/reject"): "proposal.reject",
    ("post", "/v1/proposals/{proposal_id}/route"): "proposal.route",
    ("post", "/v1/proposals/{proposal_id}/follow-up"): "proposal.follow_up",
    ("post", "/v1/proposals/{proposal_id}/undo"): "proposal.undo",
    ("post", "/v1/suggestions/{suggestion_id}/adopt"): "suggestion.resolve",
    ("post", "/v1/suggestions/{suggestion_id}/dismiss"): "suggestion.resolve",
}
# A person's acts: every resolution, decision and sign-off (contract §5; INV-1, ADR-005).
HUMAN_ONLY = {
    "sign_off.create",
    "sign_off.bulk",
    "sign_off.prepare",
    "sign_off.review",
    "sign_off.manager",
    "sign_off.partner",
    "sign_off.eqr",
    "review_note.raise",
    "review_note.respond",
    "review_note.clear",
    "review_note.withdraw",
    "decision.decide",
    "decision.request_analysis",
    "decision.notify",
    "decision.reassess",
    "proposal.approve",
    "proposal.reject",
    "proposal.route",
    "proposal.follow_up",
    "proposal.undo",
    "suggestion.resolve",
}
# The rows the contract says deny `system` explicitly at the matrix (§5, parts 1 and 2).
SYSTEM_DENY_EXPLICIT = {
    "sign_off.create",
    "sign_off.bulk",
    "review_note.withdraw",
    "decision.decide",
    "decision.request_analysis",
    "decision.notify",
    "decision.reassess",
    "proposal.approve",
    "proposal.reject",
    "proposal.route",
    "proposal.follow_up",
    "proposal.undo",
    "suggestion.resolve",
}
READS = {"sign_off.read", "review_note.read", "human_gate.read", "decision.read", "proposal.read"}
NON_FIRM = {"agent", "system", "client_admin", "client_contributor"}

# Every model of stubs 1 and 2 (the C3 v1 schema the consumers build against).
MODELS: list[type[BaseModel]] = [
    v
    for module in (review_contract, agents_contract)
    for v in vars(module).values()
    if isinstance(v, type) and issubclass(v, BaseModel) and v.__module__ == module.__name__
]


@pytest.mark.parametrize(("method", "path"), sorted(ROUTES))
def test_c3_each_route_declares_its_action_and_the_stub_answers(method: str, path: str) -> None:
    op = PATHS[path][method]
    assert op["x-abacus-action"] == ROUTES[(method, path)]
    assert {"404", "501"} <= set(cast(Json, op["responses"]))


def test_c3_bulk_sign_off_takes_an_idempotency_key() -> None:
    params = cast(list[Json], PATHS["/v1/sign-offs:bulk"]["post"].get("parameters", []))
    found = [p for p in params if p["name"] == "Idempotency-Key" and p["in"] == "header"]
    assert found and found[0]["required"] is True


def _ctx() -> AuthContext:
    user = uuid.uuid4()
    return AuthContext(
        TenantContext(uuid.uuid4(), "human", str(user)), user, uuid.uuid4(), None, None
    )


# Live with the flag on (no longer 501): P-04-T16 serves the human gates from the projection
# (tests/integration/backfill/test_p04t16_human_gate_projector.py); P-04-T18 the ladder,
# eligibility and sign-off (tests/integration/test_p04t18_sign_off_service.py); P-04-T21 the
# notes, T22 bulk sign-off and T23 decision cards (tests/integration/test_p04t2[123]_*.py).
LIVE = frozenset(
    {
        "human_gate_list_route",
        "sign_off_ladder_route",
        "sign_off_eligibility_route",
        "sign_off_route",
        "sign_off_bulk_route",
        "review_note_list_route",
        "review_note_route",
        "review_note_raise_route",
        "review_note_respond_route",
        "review_note_clear_route",
        "review_note_withdraw_route",
        "decision_card_list_route",
        "decision_card_route",
        "decision_card_decide_route",
        "decision_card_analysis_request_route",
        "decision_card_notify_route",
        "decision_card_reassess_route",
    }
)


_ENDPOINTS: list[tuple[ModuleType, Callable[..., Awaitable[object]]]] = [
    (module, cast(Callable[..., Awaitable[object]], route.endpoint))
    for module, routers in (
        (
            review_contract,
            (
                review_contract.sign_offs_router,
                review_contract.review_notes_router,
                review_contract.human_gates_router,
                review_contract.decision_cards_router,
            ),
        ),
        (agents_contract, (agents_contract.proposals_router, agents_contract.suggestions_router)),
    )
    for router in routers
    for route in router.routes
    if isinstance(route, APIRoute)
]


def test_c3_the_endpoints_are_the_routes_above() -> None:
    assert len(_ENDPOINTS) == len(ROUTES)


@pytest.mark.parametrize(
    ("module", "endpoint"), _ENDPOINTS, ids=[e.__name__ for _m, e in _ENDPOINTS]
)
async def test_c3_flag_off_is_404_and_flag_on_is_501(
    module: ModuleType,
    endpoint: Callable[..., Awaitable[object]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Each route handler itself, with the flag read stubbed: off 404, on 501 (§2, §6)."""
    handler = endpoint
    params = inspect.signature(handler).parameters
    args = {name: (_ctx() if name == "ctx" else None) for name in params}
    seen: list[object] = []

    async def off(_tenant: object, flag: object) -> bool:
        seen.append(flag)
        return False

    async def on(_tenant: object, _flag: object) -> bool:
        return True

    monkeypatch.setattr(module, "flag_enabled", off)
    with pytest.raises(NotFound):
        await handler(**args)
    assert seen == [REVIEW_GRAMMAR_API]
    if handler.__name__ in LIVE:
        return  # served with the flag on; its integration tests cover the answers
    monkeypatch.setattr(module, "flag_enabled", on)
    with pytest.raises(NotImplementedYet):
        await handler(**args)


@pytest.mark.parametrize("action", sorted(HUMAN_ONLY))
def test_c3_every_resolution_denies_the_agent_and_system(action: str) -> None:
    decisions = RULES[action].decisions
    assert decisions.get("agent") == "deny"
    assert decisions.get("system", "deny") == "deny"  # no cell is a deny (authorise layer 2)
    assert not {r for r, d in decisions.items() if d != "deny"} & NON_FIRM


@pytest.mark.parametrize("action", sorted(SYSTEM_DENY_EXPLICIT))
def test_c3_the_named_rows_deny_system_explicitly(action: str) -> None:
    assert RULES[action].decisions.get("system") == "deny"


@pytest.mark.parametrize("action", sorted(READS))
def test_c3_reads_are_firm_roles_only(action: str) -> None:
    granted = {r for r, d in RULES[action].decisions.items() if d != "deny"}
    assert granted and not granted & NON_FIRM


def test_c3_the_agent_only_proposes() -> None:
    assert RULES["proposal.create"].decisions == {"agent": "task_scope"}
    assert RULES["suggestion.create"].decisions.get("agent") == "task_scope"


@pytest.mark.parametrize(
    ("schema", "field", "enum", "registry_object"),
    [
        ("ReviewNoteItemOut", "status", "ReviewNoteStatus", "review_note"),
        ("DecisionCardItemOut", "status", "DecisionCardStatus", "decision_card"),
        ("AgentProposalOut", "state", "ProposalStatus", "proposal"),
        ("AgentSuggestionOut", "status", "SuggestionStatus", "suggestion"),
    ],
)
def test_c3_statuses_are_the_registry_enums(
    schema: str, field: str, enum: str, registry_object: str
) -> None:
    assert schema_ref(schema, field) == f"#/components/schemas/{enum}"
    assert SCHEMAS[enum]["enum"] == stored_codes(registry_object)


def test_c3_the_sign_off_slot_is_derived_never_a_stored_status() -> None:
    """`signed` and `stale` are derived (§4): the wire has a computed `stale`, no status."""
    assert stored_codes("sign_off_slot") == []
    fields = review_contract.SignOffOut.model_fields
    assert "status" not in fields and fields["stale"].annotation is bool


def test_c3_schema_v1_migrations_agree_with_the_wire() -> None:
    """The three review migrations' CHECK lists are the enums and literals on the wire."""
    m93 = migration("0093_review_core.py")
    m94 = migration("0094_review_cards_checkpoints_issues.py")
    m95 = migration("0095_agent_suggestions_proposals.py")
    assert check_list(m94, "status", "decision_cards") == stored_codes("decision_card")
    assert check_list(m95, "status", "suggestions") == stored_codes("suggestion")
    assert check_list(m95, "state", "proposals") == stored_codes("proposal")
    assert check_list(m95, "decision", "proposal_decisions") == list(
        get_args(agents_contract.ProposalDecisionKind)
    )
    assert check_list(m95, "reason_code", "proposal_decisions") == list(
        get_args(agents_contract.RejectReason)
    )
    assert check_list(m95, "decision", "suggestion_decisions") == list(
        get_args(agents_contract.SuggestionDecisionKind)
    )
    assert "CHECK (status IN ('open', 'responded', 'cleared', 'closed', 'withdrawn'))" in m93
    assert stored_codes("review_note") == ["open", "responded", "cleared", "closed", "withdrawn"]
    assert check_list(m93, "kind", "human_gates") == list(get_args(review_contract.GateKind))
    assert check_list(m93, "state", "human_gates") == list(get_args(review_contract.GateState))


def test_c3_schema_v1_human_only_rows_are_checked_at_the_data_layer() -> None:
    """INV-1 below the matrix: the sign-off, decision and proposal and suggestion decision rows
    carry their human-only CHECK (contract §5)."""
    assert "sign_offs_human_only" in migration("0093_review_core.py")
    assert "decisions_human_only" in migration("0094_review_cards_checkpoints_issues.py")
    m95 = migration("0095_agent_suggestions_proposals.py")
    assert "proposal_decisions_human_only" in m95 and "suggestion_decisions_human_only" in m95


@pytest.mark.parametrize("model", MODELS, ids=[m.__name__ for m in MODELS])
def test_c3_every_field_carries_a_classification(model: type[BaseModel]) -> None:
    assert unclassified_fields(model) == []


# --- Generated names: what the consumers import ------------------------------------------------

C3_PATHS = {path for _method, path in ROUTES}
# TASK-422 gave the C3 models names no older model holds (#284); the client imports these.
C3_NAMES = (
    "AgentProposalOut",
    "AgentSuggestionOut",
    "ReviewNoteDetailOut",
    "CardDecisionOut",
    "CardDecideIn",
    "DecisionCardOut",
    "SignOffEligibilityOut",
    "BulkSignOffOut",
)


def test_c3_operation_ids_are_unique_in_the_document() -> None:
    ours = {cast(str, op.get("operationId")) for p in C3_PATHS for op in PATHS[p].values()}
    others = {
        cast(str, op.get("operationId"))
        for p, ops in PATHS.items()
        if p not in C3_PATHS
        for op in ops.values()
    }
    assert len(ours) == len(ROUTES) and not ours & others


@pytest.mark.parametrize("name", C3_NAMES)
def test_c3_models_have_their_own_component_names(name: str) -> None:
    assert name in SCHEMAS
    assert not [n for n in SCHEMAS if n.startswith("abacus__") and n.endswith(f"__{name}")]
