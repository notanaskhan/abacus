# ac-test-author: ayushkbhatia
"""Team, acceptance, independence and conflicts v1: the consumer contract tests (P-07-T31;
`docs/contracts/acceptance-independence.md` §3, §4, §6, §8; SPEC-332 AC-6, AC-18, AC-24, AC-25;
screen contracts ENG-05, CLI-07 and CLI-08).

What ENG-05, CLI-07 and CLI-08 rely on, read from the OpenAPI document as the generated client
reads it, plus the contract's §8 example frames validated against the models. Schema shape only;
they run in the provider's CI against the stub and keep holding once the routes are live. The
stub suite (`test_acceptance_independence_stub.py`) owns routes, actions, flags and the matrix;
this file owns what a screen renders and sends:

- the decision and conclusion option sets, on the way in and on the way out, are the dock's three
  options (CLI-07 `dock.options`, CLI-08 `conclude.options`) and the C2 registry's codes;
- every C2 status field is exactly its registry object's codes (§4);
- the redacted conflict row (DEC-64, AC-24): `redacted` and `match_kind` only, nothing that names,
  links to or counts a walled client;
- the ENG-05 roster, team-approval footer and EQR picker carry what their artboards render.
"""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import cast

import pytest
import yaml
from pydantic import TypeAdapter, ValidationError

from abacus.api.export_openapi import document
from abacus.modules.organisations import conflicts_contract

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
SCHEMAS = cast(dict[str, Json], cast(Json, DOC["components"])["schemas"])
VOCABULARY = Path(__file__).resolve().parents[4] / "docs" / "product" / "status-vocabulary.yaml"
OBJECTS = cast(dict[str, Json], yaml.safe_load(VOCABULARY.read_text())["objects"])
E = "/v1/engagements/{engagement_id}"

# Typed from the contract and the screen copy, never imported from the provider.
DECISION_OPTIONS = {"accept", "accept_with_conditions", "decline"}  # CLI-07 dock.options
CONCLUSION_OPTIONS = {"independent", "independent_with_safeguards", "not_independent"}
CONFIRMATION = {"requested", "confirmed", "declined"}  # ENG-05 / CLI-08 chip
WALL_NAME = re.compile(r"(hidden|walled|wall_|_wall|redacted_count|restricted_count)")


def _props(schema: str) -> dict[str, Json]:
    return cast(dict[str, Json], SCHEMAS[schema].get("properties", {}))


def _required(schema: str) -> set[str]:
    return set(cast(list[str], SCHEMAS[schema].get("required", [])))


def _plain(prop: Json) -> Json:
    """The non-null branch of an optional property."""
    if "anyOf" in prop:
        return next(p for p in cast(list[Json], prop["anyOf"]) if p.get("type") != "null")
    return prop


def _enum(schema: str, field: str) -> set[str] | None:
    """The closed set a field takes, through a `$ref` to a generated enum; None when open."""
    prop = _plain(_props(schema)[field])
    if "$ref" in prop:
        prop = SCHEMAS[cast(str, prop["$ref"]).rsplit("/", 1)[-1]]
    found = prop.get("enum")
    return set(cast(list[str], found)) if found is not None else None


def _codes(obj: str) -> set[str]:
    return set(cast(dict[str, object], OBJECTS[obj]["codes"]))


def _body(method: str, path: str) -> str:
    schema = cast(
        Json,
        cast(
            Json,
            cast(Json, cast(Json, PATHS[path][method]["requestBody"])["content"])[
                "application/json"
            ],
        )["schema"],
    )
    return cast(str, schema["$ref"]).rsplit("/", 1)[-1]


def _ok(method: str, path: str) -> str:
    responses = cast(dict[str, Json], PATHS[path][method]["responses"])
    code = next(c for c in ("200", "201") if c in responses)
    schema = cast(
        Json, cast(Json, cast(Json, responses[code]["content"])["application/json"])["schema"]
    )
    if schema.get("type") == "array":
        schema = cast(Json, schema["items"])
    return cast(str, schema["$ref"]).rsplit("/", 1)[-1]


# --- CLI-07: the three-option decision (SPEC-332 AC-6, AC-7) ----------------------------------


def test_ac6_the_decision_route_takes_and_returns_the_docks_three_options() -> None:
    path = f"{E}/acceptance/decision"
    sent, returned = _body("post", path), _ok("post", path)
    assert sent == "AcceptanceDecisionIn"
    assert _enum(sent, "option") == DECISION_OPTIONS
    assert {"option", "rationale", "seen_version"} <= _required(sent)
    assert "conditions" in _props(sent)
    record = _props(returned)
    decision = _plain(record["decision"])
    decision_schema = cast(str, decision["$ref"]).rsplit("/", 1)[-1]
    assert _enum(decision_schema, "option") == DECISION_OPTIONS
    assert {"rationale", "decided_by", "decided_at"} <= _required(decision_schema)
    # 409 decision_locked / review_required and 422 rationale_required are documented.
    assert {"409", "422"} <= set(cast(Json, PATHS[path]["post"]["responses"]))


def test_ac9_a_condition_carries_an_assignee_and_an_optional_due_date() -> None:
    for schema in ("ConditionIn", "AcceptanceConditionOut"):
        assert {"text", "assignee_user_id"} <= _required(schema)
        assert "due_on" in _props(schema) and "due_on" not in _required(schema)
    assert {"completed_at", "completed_by"} <= set(_props("AcceptanceConditionOut"))


def test_ac1_the_record_carries_what_cli07_renders() -> None:
    record = _props("AcceptanceRecordOut")
    assert {
        "kind",
        "status",
        "template_version_id",
        "template_name",
        "risk_rating",
        "sections",
        "flags",
        "decision",
        "conditions",
        "risk_partner_review",
        "prior",
        "version",
        "allowed_actions",
    } <= set(record)
    assert _enum("AcceptanceRecordOut", "kind") == {
        "new_client",
        "new_engagement_existing_client",
        "continuance",
    }
    assert _enum("AcceptanceRecordOut", "status") == _codes("acceptance_record")
    assert _enum("AcceptanceSectionOut", "answer_state") == {
        "pending",
        "complete",
        "flag",
        "manual_check_open",
        "manual_check_done",
    }
    assert _enum("AcceptanceFlagOut", "severity") == {"low", "medium", "high"}
    assert {"authored_by", "authored_at"} <= _required("AcceptanceFlagOut")
    assert _enum("SourceRefOut", "kind") == {"evidence_version", "request_item"}


def test_ac4_the_risk_rating_is_the_contracts_three_codes() -> None:
    assert _enum("AcceptanceRecordOut", "risk_rating") == {"low", "moderate", "high"}


# --- CLI-08: the conclusion and the confirmations (SPEC-332 AC-17 to AC-19) ---------------------


def test_ac18_the_conclusion_route_takes_and_returns_the_three_registry_options() -> None:
    path = f"{E}/independence/conclude"
    sent, returned = _body("post", path), _ok("post", path)
    assert sent == "ConcludeIn"
    assert _enum(sent, "option") == CONCLUSION_OPTIONS == _codes("independence_conclusion")
    assert "safeguards" in _props(sent)
    assert returned == "IndependenceConclusionOut"
    assert _enum(returned, "option") == CONCLUSION_OPTIONS
    assert {"concluded_by", "concluded_at"} <= _required(returned)
    assert "supersedes_id" in _props(returned)
    summary = _plain(_props("IndependenceSummaryOut")["conclusion"])
    assert cast(str, summary["$ref"]).endswith("/IndependenceConclusionOut")
    # 409 independence_preconditions_unmet is documented.
    assert "409" in cast(Json, PATHS[path]["post"]["responses"])


def test_ac17_the_summary_carries_cli08s_count_members_and_blockers() -> None:
    assert {"attest_client", "confirmed", "total"} <= _required("IndependenceSummaryOut")
    assert {"members", "blockers", "ske_designee_contact_id", "allowed_actions"} <= set(
        _props("IndependenceSummaryOut")
    )
    assert _enum("MemberConfirmationOut", "confirmation") == CONFIRMATION
    assert {"user_id", "display_name", "role"} <= _required("MemberConfirmationOut")
    assert "decline_note" in _props("MemberConfirmationOut")
    # Each blocker is a reason code and an identifier (blockers as identifier facts, AC-19).
    assert {"reason_code", "ref_type", "ref_id"} <= _required("IndependenceBlockerOut")
    assert _enum("IndependenceBlockerOut", "reason_code") is not None
    for path, body in (
        (f"{E}/independence/confirm", "ConfirmIn"),
        (f"{E}/independence/decline", "DeclineIn"),
    ):
        assert _body("post", path) == body
        assert "409" in cast(Json, PATHS[path]["post"]["responses"])  # not_self
    assert {"statement_version", "statement_codes"} <= _required("ConfirmIn")
    assert _required("DeclineIn") == {"note"}


def test_ac21_nas_rotation_and_breach_events_are_codes() -> None:
    assert _enum("NasRowOut", "status") == _codes("nas_evaluation")
    assert {"review_years"} <= _required("RotationOut")
    assert {"years_served", "familiarity_flag"} <= _required("RotationRowOut")
    assert _enum("BreachEventIn", "kind") == {"evaluated", "tcwg_communicated", "remediated"}


# --- ENG-05: roster, team approval footer, EQR picker ------------------------------------------


def test_ac13_the_roster_chip_is_the_three_confirmation_states() -> None:
    assert _enum("TeamRosterMemberOut", "independence") == CONFIRMATION


def test_ac13_the_roster_carries_eng05s_columns() -> None:
    assert _ok("get", f"{E}/team") == "TeamRosterMemberOut"
    assert {"user_id", "display_name", "role"} <= _required("TeamRosterMemberOut")
    assert {"budget_hours", "shown_on_portal", "proposed_at", "independence"} <= set(
        _props("TeamRosterMemberOut")
    )
    assert {"eqr_reviewer", "specialist"} <= cast(set[str], _enum("TeamRosterMemberOut", "role"))
    # Hours are decimal strings computed in code (ADR-050), never floats.
    assert _plain(_props("TeamRosterMemberOut")["budget_hours"]).get("type") == "string"


def test_eng05_the_approval_footer_names_the_approver_and_the_changes_since() -> None:
    assert _ok("get", f"{E}/team/approval") == "TeamApprovalOut"
    assert _ok("post", f"{E}/team/approve") == "TeamApprovalOut"
    assert _body("post", f"{E}/team/approve") == "TeamApproveIn"
    assert _required("TeamApproveIn") == {"member_set_hash"}
    assert {"member_set_hash", "changed"} <= _required("TeamApprovalOut")
    assert {"approved_by", "approved_by_name", "approved_at", "added_since"} <= set(
        _props("TeamApprovalOut")
    )


def test_eng05_the_eqr_picker_shows_eligibility_per_check() -> None:
    assert _ok("get", f"{E}/eqr/candidates") == "EqrCandidateOut"
    assert {"display_name", "eligibility", "checks"} <= _required("EqrCandidateOut")
    assert _enum("EqrCandidateOut", "eligibility") == {"eligible", "not_eligible"}
    assert _enum("EqrCheckOut", "result") == {"pass", "fail", "pending", "not_assessed"}
    assert {"count", "year"} <= set(_props("EqrCheckOut"))
    assert "409" in cast(Json, PATHS[f"{E}/eqr/eligibility/approve"]["post"]["responses"])


# --- CLI-06 / CLI-08 c: the redacted conflict row (SPEC-332 AC-24, AC-25; DEC-64) ---------------


def test_ac24_the_contracts_redacted_row_is_a_valid_result() -> None:
    """Contract §8: a walled match is `redacted: true` with no client, name, ref or score."""
    frame: Json = {
        "id": str(uuid.uuid4()),
        "redacted": True,
        "match_kind": "trigram",
        "assessment": "pending",
        "matched_client_id": None,
        "matched_name": None,
        "matched_ref_type": None,
        "matched_ref_id": None,
        "score": None,
    }
    row = TypeAdapter(conflicts_contract.ConflictResultOut).validate_python(frame)
    dumped = cast(
        Json, json.loads(TypeAdapter(conflicts_contract.ConflictResultOut).dump_json(row))
    )
    for field in (
        "matched_client_id",
        "matched_name",
        "matched_ref_type",
        "matched_ref_id",
        "score",
    ):
        assert dumped.get(field) is None
    # The row needs nothing that names a client: only id, redacted, match_kind and assessment.
    assert _required("ConflictResultOut") <= {"id", "redacted", "match_kind", "assessment"}
    minimal = {k: frame[k] for k in ("id", "redacted", "match_kind", "assessment")}
    TypeAdapter(conflicts_contract.ConflictResultOut).validate_python(minimal)
    with pytest.raises(ValidationError):
        TypeAdapter(conflicts_contract.ConflictResultOut).validate_python(
            {**minimal, "match_kind": "fuzzy"}
        )


def test_ac24_no_conflict_schema_counts_or_flags_walled_matches() -> None:
    for name in ("ConflictCheckOut", "ConflictResultOut", "ConflictCheckIn"):
        assert not [p for p in _props(name) if WALL_NAME.search(p)], name
    # The one count on a check is the names searched (1 to 50), not matches.
    counts = [p for p in _props("ConflictCheckOut") if "count" in p]
    assert counts == ["names_count"]
    assert _enum("ConflictCheckOut", "outcome") == {"pending", "clear", "hits"}


def test_ac25_assessments_are_the_registry_and_clearing_takes_a_code_and_reason() -> None:
    assert _enum("ConflictResultOut", "assessment") == _codes("conflict_assessment")
    # Contract §4: `conflict` joined the registry with P-07-T36; every clearance code is a
    # registry assessment, and `pending` is never a clearance.
    clearance = cast(set[str], _enum("ConflictClearIn", "assessment"))
    assert clearance == _codes("conflict_assessment") - {"pending"}
    assert _required("ConflictClearIn") == {"assessment", "reason"}
    path = "/v1/conflict-checks/{check_id}/results/{result_id}/clear"
    assert _body("post", path) == "ConflictClearIn"
    assert _ok("post", path) == "ConflictResultOut"
    assert _enum("ScreeningRecordIn", "screening_list") == {
        "ofac_sdn",
        "adverse_media",
        "restricted_entities",
    }
    assert {"recorded_by", "recorded_at"} <= _required("ScreeningRecordOut")
