"""C3 v1 consumer tests (P-04-T12), stub 3 as a whole: every issue, checkpoint and field route
declares its one matrix action and answers 404 with `review.grammar_api` off and 501 with it on;
every part 3 write and resolution denies the agent and system principals; the status enums are the
registry's stored codes; migrations 0093 and 0094 agree with the wire; and stub 3 is additive,
with names no older model holds. `docs/contracts/review-grammar.md` §2 to §6, part 3."""

from __future__ import annotations

import inspect
import uuid
from collections.abc import Awaitable, Callable
from typing import Final, cast, get_args

import pytest
from fastapi.routing import APIRoute
from pydantic import BaseModel

from abacus.kernel._flags import REVIEW_GRAMMAR_API
from abacus.kernel.classification import unclassified_fields
from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.modules.identity.api import AuthContext
from abacus.modules.identity.authz.matrix import RULES
from abacus.modules.review import contract as c3

from ._c3 import PATHS, SCHEMAS, Json, check_list, migration, schema_ref, stored_codes

_F = "/v1/fields/{target_type}/{target_id}/{field_key}"
# (method, path) -> the one matrix action (contract §2, part 3).
ROUTES: dict[tuple[str, str], str] = {
    ("get", "/v1/issues"): "issue.read",
    ("get", "/v1/issues/{issue_id}"): "issue.read",
    ("post", "/v1/issues"): "issue.create",
    ("patch", "/v1/issues/{issue_id}"): "issue.update",
    ("post", "/v1/issues/{issue_id}/resolve"): "issue.resolve",
    ("post", "/v1/issues/{issue_id}/mark-not-applicable"): "issue.resolve",
    ("post", "/v1/issues/{issue_id}/verify"): "issue.verify",
    ("post", "/v1/issues/{issue_id}/reopen"): "issue.reopen",
    ("post", "/v1/issues/{issue_id}/send-to-client"): "issue.send_to_client",
    ("post", "/v1/issues/{issue_id}/fix-instructions"): "fix_instruction.set",
    ("post", "/v1/issues/fix-instructions:bulk"): "fix_instruction.set",
    ("post", "/v1/issues/{issue_id}/explanations"): "issue.explain",
    ("get", "/v1/checkpoints"): "checkpoint.read",
    ("get", "/v1/checkpoints/{checkpoint_id}"): "checkpoint.read",
    ("post", "/v1/checkpoints"): "checkpoint.create",
    ("post", "/v1/checkpoints/{checkpoint_id}/approve"): "checkpoint.approve",
    ("post", "/v1/checkpoints/{checkpoint_id}/reject"): "checkpoint.reject",
    ("post", "/v1/checkpoints/{checkpoint_id}/restore"): "checkpoint.restore",
    ("patch", "/v1/checkpoints/{checkpoint_id}"): "checkpoint.rename",
    ("get", _F + "/provenance"): "field.read",
    ("put", _F + "/value"): "field.edit",
    ("post", _F + "/references"): "field.add_reference",
    ("post", _F + "/ticks"): "field.sign_off",
}
# Resolutions and ticks: a person's decision, denied at every layer (§5; INV-1, ISSUE-001).
RESOLUTIONS = {
    "issue.resolve",
    "issue.verify",
    "issue.reopen",
    "checkpoint.approve",
    "checkpoint.reject",
    "checkpoint.restore",
    "field.sign_off",
}
# A person's acts too: every other part 3 write (§5).
PERSONS_ACTS = {
    "issue.create",
    "issue.update",
    "issue.send_to_client",
    "issue.explain",
    "fix_instruction.set",
    "checkpoint.create",
    "checkpoint.rename",
    "field.edit",
    "field.add_reference",
}
READS = {"issue.read", "checkpoint.read", "field.read"}
NON_FIRM = {"agent", "system", "client_admin", "client_contributor"}
# The 202s start an agent run; the 201s create a row (contract §3, part 3).
ACCEPTED = {
    ("post", "/v1/issues/{issue_id}/fix-instructions"),
    ("post", "/v1/issues/fix-instructions:bulk"),
    ("post", "/v1/issues/{issue_id}/explanations"),
}
CREATED = {
    ("post", "/v1/issues"),
    ("post", "/v1/checkpoints"),
    ("post", "/v1/checkpoints/{checkpoint_id}/restore"),
    ("post", _F + "/references"),
    ("post", _F + "/ticks"),
}

ROUTERS = (c3.issues_router, c3.checkpoints_router, c3.fields_router)
_ENDPOINTS: list[Callable[..., Awaitable[object]]] = [
    cast(Callable[..., Awaitable[object]], route.endpoint)
    for router in ROUTERS
    for route in router.routes
    if isinstance(route, APIRoute)
]
# Stub 3's models: everything `review/contract.py` defines below the part 3 marker.
_PART3 = inspect.getsource(c3).split("# === C3 stub PR 3 (P-04-T11)", 1)[1]
MODELS: list[type[BaseModel]] = [
    v
    for name, v in vars(c3).items()
    if isinstance(v, type)
    and issubclass(v, BaseModel)
    and v.__module__ == c3.__name__
    and f"\nclass {name}(" in _PART3
]


@pytest.mark.parametrize(("method", "path"), sorted(ROUTES))
def test_c3_part3_each_route_declares_its_action_and_the_stub_answers(
    method: str, path: str
) -> None:
    op = PATHS[path][method]
    assert op["x-abacus-action"] == ROUTES[(method, path)]
    assert {"404", "501"} <= set(cast(Json, op["responses"]))


@pytest.mark.parametrize(("method", "path"), sorted(ACCEPTED | CREATED))
def test_c3_part3_runs_answer_202_and_new_rows_201(method: str, path: str) -> None:
    expected = "202" if (method, path) in ACCEPTED else "201"
    assert expected in cast(Json, PATHS[path][method]["responses"])


def test_c3_part3_send_to_client_takes_an_idempotency_key() -> None:
    """The only part 3 route with a client-visible effect (§2; P-36)."""
    op = PATHS["/v1/issues/{issue_id}/send-to-client"]["post"]
    params = cast(list[Json], op.get("parameters", []))
    found = [p for p in params if p["name"] == "Idempotency-Key" and p["in"] == "header"]
    assert found and found[0]["required"] is True


def test_c3_part3_the_endpoints_are_the_routes_above() -> None:
    assert len(_ENDPOINTS) == len(ROUTES)


def _ctx() -> AuthContext:
    user = uuid.uuid4()
    return AuthContext(
        TenantContext(uuid.uuid4(), "human", str(user)), user, uuid.uuid4(), None, None
    )


# P-04-T30: these issue routes are live (their flag-on behaviour is the integration suite's).
ISSUES: Final = frozenset(
    {"issue_list_route", "issue_route", "issue_create_route", "issue_update_route"}
)
_STUBBED = [e for e in _ENDPOINTS if e.__name__ not in ISSUES]
# Live with the flag on (no longer 501): P-04-T32 serves the checkpoints, P-04-T35 the fields
# (tests/integration/backfill/test_p04t32_checkpoints.py; DEC-804).
LIVE: Final = frozenset(
    {
        "checkpoint_history_route",
        "checkpoint_route",
        "checkpoint_create_route",
        "checkpoint_approve_route",
        "checkpoint_reject_route",
        "checkpoint_restore_route",
        "checkpoint_rename_route",
        # P-04-T35 serves the field routes (tests/integration/backfill/test_p04t35_field_values.py;
        # DEC-1050).
        "field_provenance_route",
        "field_edit_route",
        "field_reference_route",
        "field_tick_route",
        # P-04-T31 (DEC-828): resolutions, fix instructions and send-to-client
        # (tests/integration/backfill/test_p04t31_issues_part2.py).
        "issue_resolve_route",
        "issue_verify_route",
        "issue_reopen_route",
        "issue_not_applicable_route",
        "issue_send_to_client_route",
        "fix_instructions_route",
        "fix_instructions_bulk_route",
    }
)


@pytest.mark.parametrize("endpoint", _STUBBED, ids=[e.__name__ for e in _STUBBED])
async def test_c3_part3_flag_off_is_404_and_flag_on_is_501(
    endpoint: Callable[..., Awaitable[object]], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each route handler itself, with the flag read stubbed: off 404, on 501 (§2, §6)."""
    params = inspect.signature(endpoint).parameters
    args = {name: (_ctx() if name == "ctx" else None) for name in params}
    seen: list[object] = []

    async def off(_tenant: object, flag: object) -> bool:
        seen.append(flag)
        return False

    async def on(_tenant: object, _flag: object) -> bool:
        return True

    monkeypatch.setattr(c3, "flag_enabled", off)
    with pytest.raises(NotFound):
        await endpoint(**args)
    assert seen == [REVIEW_GRAMMAR_API]
    if endpoint.__name__ in LIVE:
        return  # served with the flag on; its integration tests cover the answers
    monkeypatch.setattr(c3, "flag_enabled", on)
    with pytest.raises(NotImplementedYet):
        await endpoint(**args)


@pytest.mark.parametrize("action", sorted(RESOLUTIONS | PERSONS_ACTS))
def test_c3_part3_every_write_denies_the_agent_and_system_explicitly(action: str) -> None:
    decisions = RULES[action].decisions
    assert decisions.get("agent") == "deny" and decisions.get("system") == "deny"
    assert not {r for r, d in decisions.items() if d != "deny"} & NON_FIRM


@pytest.mark.parametrize("action", sorted(RESOLUTIONS))
def test_c3_part3_no_support_or_client_principal_resolves(action: str) -> None:
    decisions = RULES[action].decisions
    granted = {r for r, d in decisions.items() if d != "deny"}
    assert granted and not {r for r in granted if r.startswith(("platform_support", "client_"))}


@pytest.mark.parametrize("action", sorted(READS))
def test_c3_part3_reads_are_firm_roles_only(action: str) -> None:
    granted = {r for r, d in RULES[action].decisions.items() if d != "deny"}
    assert granted and not granted & NON_FIRM


def test_c3_part3_the_agent_only_proposes_a_checkpoint() -> None:
    """`checkpoint.propose` has no route and is the agent's only part 3 cell (§5); the system
    proposes an engine import's checkpoint (P-04-T32, DEC-804)."""
    assert RULES["checkpoint.propose"].decisions == {"system": "allow", "agent": "task_scope"}
    assert "checkpoint.propose" not in set(ROUTES.values())
    agent_cells = {
        a
        for a, r in RULES.items()
        if a.split(".", 1)[0] in {"issue", "fix_instruction", "checkpoint", "field"}
        and r.decisions.get("agent") not in (None, "deny")
    }
    assert agent_cells == {"checkpoint.propose"}


QC_REVIEWER_WRITES = {"issue.create", "issue.explain", "field.sign_off"}


@pytest.mark.parametrize("action", sorted(RESOLUTIONS | PERSONS_ACTS))
def test_c3_part3_the_qc_reviewer_role_writes_only_what_it_writes_elsewhere(action: str) -> None:
    """Tax Reviewer is a work-item function, not the repo's read-only QC `reviewer` role
    (DEC-21), which raises an issue as it raises a note, asks for an explanation, and ticks a
    field as it holds `sign_off.create` (§2, DEC-145)."""
    granted = RULES[action].decisions.get("reviewer", "deny") != "deny"
    assert granted == (action in QC_REVIEWER_WRITES)


def test_c3_part3_preparers_edit_and_seniors_and_above_review() -> None:
    """DEC-84: preparers edit, reviewers propose; approving and verifying is senior and above
    until P-04-T15's function conditions narrow them."""
    assert RULES["field.edit"].decisions.get("staff") == "allow"
    for action in ("checkpoint.approve", "checkpoint.reject", "checkpoint.restore"):
        assert RULES[action].decisions.get("staff", "deny") == "deny"
    assert RULES["issue.verify"].decisions.get("staff", "deny") == "deny"
    assert RULES["sign_off.create"].decisions.get("reviewer") == "allow"


@pytest.mark.parametrize(
    ("schema", "field", "enum", "registry_object"),
    [
        ("IssueItemOut", "status", "IssueStatus", "issue"),
        ("IssueItemOut", "priority", "IssueSeverityStatus", "issue_severity"),
        ("CheckpointItemOut", "status", "CheckpointStatus", "checkpoint"),
        ("IssueFixRunOut", "status", "AgentRunStatus", "agent_run"),
        ("FieldFlagOut", "status", "ReviewNoteStatus", "review_note"),
    ],
)
def test_c3_part3_statuses_are_the_registry_enums(
    schema: str, field: str, enum: str, registry_object: str
) -> None:
    assert schema_ref(schema, field) == f"#/components/schemas/{enum}"
    assert SCHEMAS[enum]["enum"] == stored_codes(registry_object)


def test_c3_part3_derived_words_are_computed_never_stored() -> None:
    """`current` (checkpoint) and every `field_value` word are derived (§4): booleans on the
    wire, no status field."""
    assert stored_codes("field_value") == []
    assert c3.CheckpointItemOut.model_fields["current"].annotation is bool
    assert c3.FieldVersionOut.model_fields["unsupported"].annotation is bool
    assert c3.FieldTickOut.model_fields["stale"].annotation is bool
    assert "status" not in c3.FieldVersionOut.model_fields


def test_c3_part3_issues_agree_with_migration_0094() -> None:
    m94 = migration("0094_review_cards_checkpoints_issues.py")
    assert check_list(m94, "kind", "issues") == list(get_args(c3.IssueKind))
    assert check_list(m94, "priority", "issues") == stored_codes("issue_severity")
    # The issues CHECK also holds the audit-route codes, which AUD-15's contract carries (§4).
    assert check_list(m94, "status", "issues") == (
        stored_codes("issue") + stored_codes("issue_audit_route")
    )
    assert check_list(m94, "event", "issue_events") == list(get_args(c3.IssueEvent))
    assert check_list(m94, "scope", "issue_events") == list(get_args(c3.FixScope))
    assert check_list(m94, "link_kind", "issue_links") == list(get_args(c3.IssueLinkKind))
    blocks = ", ".join(f"'{b}'" for b in get_args(c3.IssueBlock))
    assert f"blocks <@ ARRAY[{blocks}]::text[]" in m94


def test_c3_part3_checkpoints_agree_with_migration_0094() -> None:
    m94 = migration("0094_review_cards_checkpoints_issues.py")
    assert check_list(m94, "author_kind", "checkpoints") == list(get_args(c3.CheckpointAuthorKind))
    assert check_list(m94, "cause", "checkpoints") == list(get_args(c3.CheckpointCause))
    assert check_list(m94, "status", "checkpoints") == stored_codes("checkpoint")
    assert check_list(m94, "decision", "checkpoint_decisions") == list(
        get_args(c3.CheckpointDecisionKind)
    )


def test_c3_part3_field_versions_agree_with_migration_0093() -> None:
    m93 = migration("0093_review_core.py")
    assert check_list(m93, "value_kind", "field_value_versions") == list(get_args(c3.ValueKind))
    # `policy` is in the CHECK but dormant (fvv_policy_dormant), so it is never on the wire.
    sources = check_list(m93, "value_source", "field_value_versions")
    assert sources == [*get_args(c3.ValueSource), "policy"]
    assert check_list(m93, "cause", "field_value_versions") == list(get_args(c3.ValueCause))


def test_c3_part3_human_only_rows_are_checked_at_the_data_layer() -> None:
    """INV-1 below the matrix (§5): checkpoint decisions and issue resolutions are a person's,
    and every human edit of a field carries its citation note."""
    m94 = migration("0094_review_cards_checkpoints_issues.py")
    assert "checkpoint_decisions_human_only" in m94
    assert "issue_events_resolution_by_a_person" in m94
    m93 = migration("0093_review_core.py")
    assert "fvv_human_edits_cite" in m93 and "fvv_policy_dormant" in m93


def test_c3_part3_has_its_models() -> None:
    assert len(MODELS) >= 40


@pytest.mark.parametrize("model", MODELS, ids=[m.__name__ for m in MODELS])
def test_c3_part3_every_field_carries_a_classification(model: type[BaseModel]) -> None:
    assert unclassified_fields(model) == []


# --- Additive, with names of its own (handshake rule 5; #284) ---------------------------------

P3_PATHS = {path for _method, path in ROUTES}
OLDER_PATHS = {
    "/v1/sign-offs",
    "/v1/sign-offs/eligibility",
    "/v1/sign-offs:bulk",
    "/v1/review-notes",
    "/v1/human-gates",
    "/v1/decision-cards",
    "/v1/proposals/{ref}",
}


def test_c3_part3_operation_ids_are_unique_in_the_document() -> None:
    ours = [cast(str, op.get("operationId")) for p in P3_PATHS for op in PATHS[p].values()]
    others = {
        cast(str, op.get("operationId"))
        for p, ops in PATHS.items()
        if p not in P3_PATHS
        for op in ops.values()
    }
    assert len(set(ours)) == len(ours) == len(ROUTES) and not set(ours) & others


@pytest.mark.parametrize("model", MODELS, ids=[m.__name__ for m in MODELS])
def test_c3_part3_models_have_their_own_component_names(model: type[BaseModel]) -> None:
    """A collision would module-prefix both models and rename a frozen type."""
    name = model.__name__
    assert not [n for n in SCHEMAS if n.startswith("abacus__") and n.endswith(f"__{name}")]


def test_c3_part3_left_parts_1_and_2_where_they_were() -> None:
    """Additive: the stub 1 and 2 paths are still served, and none of them is under a part 3
    prefix."""
    assert set(PATHS) >= OLDER_PATHS
    assert not P3_PATHS & OLDER_PATHS
