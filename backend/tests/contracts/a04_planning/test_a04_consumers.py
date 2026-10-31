"""A-04's consumer view of the provider contracts it reads (A-04-T05; TASK-2709; SPEC-620).

Chapter 01 §1.3.2 steps 1 and 3: the consumer pins what it reads, in the providers' stage 2.
Five providers, five suites:

- **C3 review grammar** (P-04): the decision-kind registration A-04's three kinds use
  (`planning_materiality`, `significant_risk`, `service_org_reliance`), raising a card with the
  agent's recommendation as a tag, the decide, notify and analysis routes, the `workpaper`
  reviewable and its facts, `record_value` and the suggestion appliers.
- **C4 citations** (P-03): the `workpaper_cell`, `methodology_step` and `document_text` kinds, the
  anchor and claim shapes and the verifier registration.
- **C9 ledger** (A-02, A-03): the Unadjusted and Final layers, the layer view's named totals and
  groups, and the FS-line subtotals the materiality benchmarks are read from (net assets,
  contributions, benefit payments, pre-tax income).
- **Methodology programs read v1** (K-01): steps with `prepopulates`, PBC positions, levels,
  mandatory and dependencies; `step_at` for citations; the materiality range from K-02 policy.
- **C5 requests** (R-01, T-02): the request-item and follow-up drafts and the questionnaire draft
  A-04 prefills (a person sends each).

Renaming or removing any field or argument A-04 reads fails here.
"""

from __future__ import annotations

import dataclasses
import inspect
import json
import typing
from typing import cast

import pytest

from abacus.api.export_openapi import document
from abacus.modules.evidence import api as evidence
from abacus.modules.identity.authz import _matrix
from abacus.modules.ledger import api as ledger
from abacus.modules.methodology import api as methodology
from abacus.modules.review import api as review

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
SCHEMAS = cast(dict[str, Json], cast(Json, DOC["components"])["schemas"])


def _props(schema: str) -> set[str]:
    return set(cast(Json, SCHEMAS[schema].get("properties", {})))


def _fields(cls: type) -> set[str]:
    return {f.name for f in dataclasses.fields(cls)}


def _params(fn: object) -> set[str]:
    return set(inspect.signature(cast(typing.Callable[..., object], fn)).parameters)


def _schema_with(*props: str) -> str:
    """The schema carrying every named property (provider names may be qualified)."""
    found = [k for k in SCHEMAS if set(props) <= _props(k)]
    assert found, props
    return found[0]


# --- C3: the review grammar ----------------------------------------------------------------------


def test_c3_decision_kinds_register_with_the_fields_a04_declares() -> None:
    # T12 (planning_materiality: EP, fresh MFA, reassess), T18 (significant_risk: per-subject
    # outcomes, no MFA, OQ-14), T31 (service_org_reliance: EP, fresh MFA).
    assert {
        "code",
        "reserved_role",
        "options",
        "questions",
        "reassess",
        "mfa_max_age_s",
    } <= _fields(review.DecisionKind)
    assert callable(review.register_decision_kind)
    assert callable(review.decision_kind)


def test_c3_a_card_is_raised_with_the_recommendation_as_a_tag() -> None:
    assert {
        "engagement_id",
        "kind",
        "question_key",
        "work_item_id",
        "reserved_user_id",
        "recommended_option_key",
        "recommendation_suggestion_id",
    } <= _params(review.raise_decision_card)


def test_c3_decide_notify_and_analysis_routes_are_people_only() -> None:
    card = "/v1/decision-cards/{card_id}"
    assert PATHS[f"{card}/decide"]["post"]["x-abacus-action"] == "decision.decide"
    assert PATHS[f"{card}/notify"]["post"]["x-abacus-action"] == "decision.notify"
    assert PATHS[f"{card}/analysis-requests"]["post"]["x-abacus-action"] == (
        "decision.request_analysis"
    )
    assert PATHS[f"{card}/reassess"]["post"]["x-abacus-action"] == "decision.reassess"
    decide = _matrix.ACTIONS["decision.decide"]
    assert decide.get("agent") == "deny"
    assert decide.get("system") == "deny"
    assert decide.get("reserved_role") == "required"


def test_c3_the_workpaper_reviewable_and_its_facts() -> None:
    assert "workpaper" in review.reviewable_fact_types()
    assert {"target_type", "target_id", "code", "title", "content_hash", "has_content"} <= _fields(
        review.Reviewable
    )
    assert {
        "target_type",
        "target_id",
        "engagement_id",
        "content_hash",
        "version_no",
        "preparer_user_ids",
        "required_levels",
        "work_item_id",
        "citation_count",
        "uncited_count",
        "adopted_run_id",
        "adopted_run_number",
    } <= _fields(review.ReviewableFacts)
    assert callable(review.register_reviewable)
    assert callable(review.register_reviewable_facts)


def test_c3_record_value_is_the_one_cell_write_path() -> None:
    assert {
        "engagement_id",
        "target_type",
        "target_id",
        "field_key",
        "value",
        "value_source",
        "cause",
        "on_behalf_of_user_id",
        "suggestion_id",
        "citation_ids",
    } <= _params(review.record_value)
    assert callable(review.register_field_owner)


def test_c3_suggestion_appliers_and_the_resolve_routes() -> None:
    assert callable(review.register_suggestion_owner)
    for verb in ("adopt", "dismiss"):
        operation = PATHS[f"/v1/suggestions/{{suggestion_id}}/{verb}"]["post"]
        assert operation["x-abacus-action"] == "suggestion.resolve"
    assert _matrix.ACTIONS["suggestion.resolve"].get("agent") == "deny"


def test_c3_sign_offs_on_workpaper_targets() -> None:
    assert PATHS["/v1/sign-offs"]["post"]["x-abacus-action"] == "sign_off.create"
    assert _matrix.ACTIONS["sign_off.create"].get("agent") == "deny"


# --- C4: citations -------------------------------------------------------------------------------


def test_c4_the_citation_kinds_a04_cites() -> None:
    kinds = set(typing.get_args(evidence.CitationKind))
    assert {"workpaper_cell", "methodology_step", "document_text"} <= kinds


def test_c4_anchor_claim_and_verifier_registration() -> None:
    assert {"type", "id", "ref", "locator", "engagement_id", "work_item_id"} <= _fields(
        evidence.CitationAnchor
    )
    assert {"kind", "locator", "quote", "value"} <= _fields(evidence.CitationClaim)
    assert {"kind", "verifier", "display", "version"} <= _params(evidence.register_citable)


# --- C9: the ledger layers and FS-line totals ----------------------------------------------------


def test_c9_the_unadjusted_and_final_layers() -> None:
    layers = set(cast(list[str], SCHEMAS["TrialBalanceLayerStatus"]["enum"]))
    assert {"unadjusted", "final"} <= layers
    assert ledger.layer_available("unadjusted")


def test_c9_the_layer_view_carries_named_totals_and_groups() -> None:
    assert {
        "trial_balance_id",
        "version_no",
        "layer",
        "period_end",
        "totals",
        "groups",
        "layers_available",
    } <= _props("TbLayerViewOut")
    assert {"key", "label", "boy", "eoy"} <= _props("TbNamedTotalOut")
    assert {"key", "label", "boy", "eoy", "lines"} <= _props("TbGroupOut")


def test_c9_fs_line_subtotals_feed_the_benchmarks() -> None:
    # Net assets, contributions, benefit payments (EBP) and pre-tax income (FS) are FS-line
    # subtotals over the mapped trial balance; the engine reads them, never the browser.
    assert {"grouping_key", "subtotal", "source_total", "off"} <= _fields(ledger.Subtotal)
    assert {"groupings", "mapped", "source_totals"} <= _params(ledger.subtotals)
    assert {"debit", "credit", "difference", "balanced"} <= _fields(ledger.Totals)
    params = {
        cast(str, p["name"])
        for p in cast(list[Json], PATHS["/v1/mapping-sets/{mapping_set_id}"]["get"]["parameters"])
    }
    assert "group_by" in params


# --- Methodology programs read v1 ----------------------------------------------------------------


def test_methodology_steps_carry_prepopulates_pbc_links_and_levels() -> None:
    step = _schema_with("step_key", "prepopulates", "pbc_positions")
    assert {
        "step_key",
        "number",
        "text",
        "level",
        "mandatory",
        "prepopulates",
        "pbc_positions",
        "depends_on_step_keys",
        "guidance",
        "standard_refs",
    } <= _props(step)


def test_methodology_step_at_for_citations() -> None:
    assert {"session", "step_key", "version_id"} <= _params(methodology.step_at)
    assert {"version_id", "version", "program_code", "step_id", "number", "text", "step_key"} <= (
        _fields(methodology.CitedStep)
    )


def test_methodology_materiality_range_from_k02_policy() -> None:
    assert {"payload", "policy", "engagement_kind"} <= _params(methodology.materiality_range_for)
    assert {
        "engagement_kind",
        "benchmark",
        "low_pct",
        "high_pct",
        "performance_materiality",
        "clearly_trivial_pct",
        "policy",
    } <= _fields(methodology.MaterialityRangeFor)


# --- C5: request and questionnaire drafts --------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "path", "action", "body", "fields"),
    [
        (
            "post",
            "/v1/engagements/{engagement_id}/request-items",
            "request_item.create",
            "RequestItemIn",
            {"description", "audit_area"},
        ),
        (
            "post",
            "/v1/follow-ups/drafts",
            "follow_up.draft",
            "FollowUpDraftsIn",
            {"request_item_ids"},
        ),
        (
            "post",
            "/v1/questionnaires",
            "questionnaire.create",
            "QuestionnaireCreateIn",
            {"kind", "work_item_id", "title", "addressed_to_contact_id", "due_on"},
        ),
    ],
)
def test_c5_the_drafts_a04_prefills(
    method: str, path: str, action: str, body: str, fields: set[str]
) -> None:
    operation = PATHS[path][method]
    assert operation["x-abacus-action"] == action
    assert fields <= _props(body)
    assert _matrix.ACTIONS[action].get("agent") != "allow", action  # absent is deny
    for client in ("client_admin", "client_contributor"):
        assert _matrix.ACTIONS[action].get(client) != "allow", (action, client)
