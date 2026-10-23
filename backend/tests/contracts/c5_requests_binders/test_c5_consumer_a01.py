"""C5 v1 consumer tests for A-01 (AUD-03; P-06-T02): the binder record and rows, the SHL-14
request record and composer bodies, the live poll, the activity feed, the chapter 09 §9.5.6
request codes, the error codes A-01's publish bar and dialogs read, and the human-only operations
A-01 puts behind a person. Schema and matrix only: the routes are stubs (`test_c5_stub.py`)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest
import yaml

from abacus.api.export_openapi import document
from abacus.kernel.errors import DomainInvalid
from abacus.kernel.uow.idempotency import IdempotencyKeyReused
from abacus.modules.identity.authz.matrix import RULES

Json = dict[str, object]
REPO = Path(__file__).resolve().parents[4]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
SCHEMAS = cast(dict[str, Json], cast(Json, DOC["components"])["schemas"])
REGISTRY = cast(
    dict[str, dict[str, dict[str, dict[str, object]]]],
    yaml.safe_load((REPO / "docs/product/status-vocabulary.yaml").read_text())["objects"],
)
CATALOGUE = cast(
    dict[str, dict[str, object]],
    yaml.safe_load((REPO / "docs/architecture/error-codes.yaml").read_text())["codes"],
)
ITEMS = "/v1/engagements/{engagement_id}/request-items/{item_id}"
BINDER = "/v1/binders/{binder_id}"


def _props(model: str) -> dict[str, Json]:
    return cast(dict[str, Json], SCHEMAS[model]["properties"])


def _required(model: str) -> set[str]:
    return set(cast(list[str], SCHEMAS[model].get("required", [])))


def _options(prop: Json) -> list[Json]:
    return cast(list[Json], prop["anyOf"]) if "anyOf" in prop else [prop]


def _ref(model: str, field: str) -> str | None:
    refs = [o["$ref"] for o in _options(_props(model)[field]) if "$ref" in o]
    return cast(str, refs[0]).rsplit("/", 1)[1] if refs else None


def _enum(model: str, field: str) -> set[str]:
    out: set[str] = set()
    for option in _options(_props(model)[field]):
        target = (
            SCHEMAS[cast(str, option["$ref"]).rsplit("/", 1)[1]] if "$ref" in option else option
        )
        out |= set(cast(list[str], target.get("enum", [])))
        if "const" in target:
            out.add(cast(str, target["const"]))
    return out


def _nullable(model: str, field: str) -> bool:
    return any(o.get("type") == "null" for o in _options(_props(model)[field]))


def _confidential(model: str) -> set[str]:
    return {name for name, prop in _props(model).items() if prop.get("cls") == "confidential"}


def _action(method: str, path: str) -> str:
    return cast(str, PATHS[path][method]["x-abacus-action"])


# --- Shapes -------------------------------------------------------------------------------------


def test_a01_the_binder_record_carries_rail_categories_and_publish_bar_facts() -> None:
    assert _required("BinderOut") == {
        "id",
        "engagement_id",
        "work_item_id",
        "name",
        "kind",
        "part",
        "status",
        "created_from",
    }
    assert {
        "recipients",
        "categories",
        "done_count",
        "total_count",
        "published_at",
        "published_by",
        "default_due_on",
        "undo_until",
        "marked_done_at",
        "marked_done_by",
        "marked_done_open_count",
        "allowed_actions",
    } <= set(_props("BinderOut"))
    assert _ref("BinderOut", "status") == "BinderStatus"
    assert _enum("BinderOut", "kind") == {
        "organizer",
        "pbc",
        "close_intake",
        "intake",
        "third_party",
    }
    assert _required("BinderCategoryOut") == {
        "id",
        "name",
        "position",
        "done_count",
        "total_count",
    }
    assert _required("BinderRecipientOut") == {"contact_id", "name"}


def test_a01_bnd02_rows_carry_status_overdue_glyph_and_linked_count() -> None:
    assert _required("BinderRequestRowOut") == {
        "id",
        "category_id",
        "title",
        "status",
        "overdue",
        "client_visible",
        "kind",
    }
    assert _ref("BinderRequestRowOut", "status") == "RequestStatus"
    assert _props("BinderRequestRowOut")["overdue"]["type"] == "boolean"
    assert _ref("BinderRequestRowOut", "screening") == "EvidenceScreeningStatus"
    assert _nullable("BinderRequestRowOut", "screening")
    assert _nullable("BinderRequestRowOut", "linked_count")  # "—" on rows with none
    assert _props("BinderRequestRowOut")["upload_count"]["type"] == "integer"
    page = _props("ListPage_BinderRequestRowOut_")
    assert {"items", "next_cursor", "total", "total_capped", "counts"} <= set(page)


def test_a01_the_shl14_record_carries_the_composer_fields_and_its_provenance() -> None:
    assert _required("RequestItemV2Out") == {
        "id",
        "engagement_id",
        "binder_id",
        "description",
        "status",
        "client_visible",
    }
    assert {
        "title",
        "category_id",
        "period_start",
        "period_end",
        "due_on",
        "wave",
        "client_assignee_user_id",
        "firm_owner_user_id",
        "supports_ref",
        "linked_ref",
        "requested_at",
        "sent_at",
        "sent_by",
        "drafted_by_run_id",
        "drafted_wording_source",
        "na_reason",
        "na_by",
        "na_at",
        "client_ignored_at",
        "undo_until",
        "allowed_actions",
    } <= set(_props("RequestItemV2Out"))
    assert _ref("RequestItemV2Out", "status") == "RequestStatus"
    assert _enum("RequestItemV2Out", "wave") == {"planning", "year_end", "sample"}
    assert _enum("RequestItemV2Out", "drafted_wording_source") == {"template", "model"}
    assert _enum("RequestItemV2Out", "na_reason") == {
        "not_applicable_this_year",
        "already_sent",
        "dont_have",
        "firm_waived",
    }


def test_a01_composer_and_dialog_bodies_are_closed_and_minimal() -> None:
    for body in ("RequestItemPatchIn", "WaiveIn", "ReturnToClientIn", "UnpublishIn", "DelegateIn"):
        assert SCHEMAS[body].get("additionalProperties") is False, body
    assert _required("RequestItemPatchIn") == set()  # absent fields are unchanged
    assert _required("WaiveIn") == {"na_reason", "note"}
    assert _enum("WaiveIn", "na_reason") == _enum("RequestItemV2Out", "na_reason")
    assert _required("ReturnToClientIn") == set()  # the note is optional
    assert _required("UnpublishIn") == {"reason"}
    assert _required("DelegateIn") == {"contact_id"}
    assert _required("DelegationOut") == {
        "request_item_id",
        "contact_id",
        "grant_id",
        "granted_by",
        "granted_at",
    }


def test_a01_the_live_poll_and_the_activity_feed_are_identifiers_and_counts() -> None:
    assert _required("BinderLiveOut") == {"items", "as_of"}
    assert _required("LiveItemOut") == {
        "request_item_id",
        "uploading_files",
        "inbox_waiting",
        "screening_running",
    }
    assert _required("ActivityEventOut") == {
        "id",
        "event_type",
        "at",
        "actor_kind",
        "target_type",
        "target_id",
    }
    assert _enum("ActivityEventOut", "actor_kind") == {"human", "agent", "system"}
    assert _props("ActivityEventOut")["via_agent"]["type"] == "boolean"  # "<person> via Agent"
    # Identifiers only: no name, wording or file name in an activity event (ADR-162).
    assert _confidential("ActivityEventOut") == set()
    assert _confidential("BinderLiveOut") == _confidential("LiveItemOut") == set()


# Contract §3: names, titles, client wording, reasons, notes and `supports_ref` are confidential;
# everything else internal; nothing Restricted.
CONFIDENTIAL = {
    "BinderRowOut": {
        "client_name",
        "work_item_label",
        "name",
        "unpublish_reason",
        "marked_done_by_name",  # P-06-T11: a person's name
    },
    "BinderOut": {"name", "unpublish_reason"},
    "BinderCategoryOut": {"name"},
    "BinderRecipientOut": {"name"},
    "BinderRequestRowOut": {"title"},
    "RequestItemV2Out": {"title", "description", "supports_ref"},
    "RequestItemPatchIn": {"title", "description", "supports_ref"},
    "WaiveIn": {"note"},
    "ReturnToClientIn": {"note"},
    "UnpublishIn": {"reason"},
}


@pytest.mark.parametrize("model", sorted(CONFIDENTIAL))
def test_a01_every_field_is_tagged_and_only_words_are_confidential(model: str) -> None:
    tags = {name: prop.get("cls") for name, prop in _props(model).items()}
    assert set(tags.values()) <= {"internal", "confidential"}, tags
    assert _confidential(model) == CONFIDENTIAL[model]


# --- Chapter 09 §9.5.6: the request status bridge, as A-01 reads it through C5 ------------------

# (repo code before F-03-T15, the C5 code, the registry's firm label)
BRIDGE = [
    ("open (firm only)", "draft", "Draft"),
    ("open", "requested", "Requested {date}"),
    ("received", "uploaded", "Uploaded \u2013 needs review"),
    ("ready_for_review", "uploaded", "Uploaded \u2013 needs review"),
    ("needs_revision", "returned", "Returned \u00b7 {reason}"),
    ("accepted", "received", "Received \u2713"),
    ("(new)", "not_applicable", "Not applicable"),
]


@pytest.mark.parametrize(("repo", "code", "label"), BRIDGE)
def test_a01_each_9_5_6_bridge_row_is_a_c5_request_code(repo: str, code: str, label: str) -> None:
    assert code in cast(list[str], SCHEMAS["RequestStatus"]["enum"]), repo
    assert REGISTRY["request"]["codes"][code]["label"] == label


def test_a01_the_c5_request_codes_are_exactly_the_bridge_and_no_repo_code_survives() -> None:
    enum = cast(list[str], SCHEMAS["RequestStatus"]["enum"])
    assert enum == ["draft", "requested", "uploaded", "received", "returned", "not_applicable"]
    assert not {"open", "ready_for_review", "needs_revision", "accepted"} & set(enum)


def test_a01_overdue_is_derived_a_boolean_never_a_status() -> None:
    assert "overdue" not in cast(list[str], SCHEMAS["RequestStatus"]["enum"])
    assert REGISTRY["request"]["codes"]["overdue"]["derived"] is True
    for model in ("BinderRequestRowOut", "RequestItemV2Out"):
        assert _props(model)["overdue"]["type"] == "boolean"


def test_a01_the_uploaded_screening_sub_states_are_the_glyph_enum() -> None:
    # §9.5.6: repo `received` is `uploaded` + not_screened; `ready_for_review` is + passed.
    assert {"passed", "not_screened"} <= set(
        cast(list[str], SCHEMAS["EvidenceScreeningStatus"]["enum"])
    )
    assert cast(list[str], SCHEMAS["EvidenceScreeningStatus"]["enum"]) == list(
        REGISTRY["evidence_screening"]["codes"]
    )


# --- Error codes (contract §6) ------------------------------------------------------------------

CODES: dict[str, int] = {
    "binder_gate_unmet": 409,
    "binder_not_draft": 409,
    "due_date_required": 422,
    "request_already_sent": 409,
    "out_of_scope": 409,
    "model_text_not_permitted": 409,
    "undo_window_closed": 409,
    "effect_started": 409,
    "idempotency_key_reused": 422,
}
# Which A-01 operation can answer which code.
RAISES: dict[tuple[str, str], set[str]] = {
    ("post", f"{BINDER}/publish"): {
        "binder_gate_unmet",
        "binder_not_draft",
        "due_date_required",
        "idempotency_key_reused",
    },
    ("post", f"{BINDER}/publish/undo"): {"undo_window_closed", "effect_started"},
    ("post", f"{ITEMS}/send"): {
        "due_date_required",
        "out_of_scope",
        "model_text_not_permitted",
        "idempotency_key_reused",
    },
    ("post", f"{ITEMS}/send/undo"): {"undo_window_closed", "effect_started"},
    ("delete", ITEMS): {"request_already_sent"},
    ("post", f"{ITEMS}/return-to-client"): {"idempotency_key_reused"},
}


@pytest.mark.parametrize(("method", "path"), sorted(RAISES))
def test_a01_each_operation_documents_the_status_of_every_code_it_raises(
    method: str, path: str
) -> None:
    documented = set(cast(Json, PATHS[path][method]["responses"]))
    assert {str(CODES[code]) for code in RAISES[(method, path)]} <= documented


@pytest.mark.parametrize("code", sorted(CODES))
def test_a01_a_catalogued_code_keeps_the_contract_status(code: str) -> None:
    # Reserved codes enter the catalogue with the class that raises them (contract §6); one
    # already there (out_of_scope) must answer as C5 says.
    if code in CATALOGUE:
        assert CATALOGUE[code]["status"] == CODES[code]


def test_a01_the_idempotency_reuse_code_is_the_kernels_422() -> None:
    assert IdempotencyKeyReused.code == "idempotency_key_reused"
    assert issubclass(IdempotencyKeyReused, DomainInvalid)  # 422


@pytest.mark.xfail(
    strict=True,
    reason=(
        "TASK-420 finding (C5 §6, ADR-139): 409 bodies carry identifier facts "
        '({"detail": "binder_gate_unmet", "facts": {"gate": "G3"}}) but every 409 is documented '
        "as ErrorOut {detail} only, so the generated client cannot type them; see #282"
    ),
)
def test_a01_the_documented_409_body_carries_identifier_facts() -> None:
    conflict = cast(Json, cast(Json, PATHS[f"{BINDER}/publish"]["post"]["responses"])["409"])
    schema = cast(Json, cast(Json, cast(Json, conflict["content"])["application/json"])["schema"])
    model = cast(str, schema["$ref"]).rsplit("/", 1)[1]
    assert "facts" in _props(model)


# --- Human-only operations A-01 puts behind a person (contract §2, §5) ---------------------------

HUMAN_ONLY = [
    ("post", f"{BINDER}/publish"),
    ("post", f"{BINDER}/publish/undo"),
    ("post", f"{BINDER}/unpublish"),
    ("put", f"{BINDER}/recipients"),
    ("put", f"{BINDER}/follow-up-override"),
    ("patch", ITEMS),
    ("delete", ITEMS),
    ("post", f"{ITEMS}/send"),
    ("post", f"{ITEMS}/send/undo"),
    ("post", f"{ITEMS}/waive"),
    ("post", f"{ITEMS}/return-to-client"),
    ("post", f"{ITEMS}/delegate"),
    ("get", f"{BINDER}/activity"),
    ("get", f"{ITEMS}/activity"),
    ("post", "/v1/engagements/{engagement_id}/evidence-versions/{version_id}/decision/accept"),
    ("post", "/v1/engagements/{engagement_id}/evidence-versions/{version_id}/decision/reject"),
]


@pytest.mark.parametrize(("method", "path"), HUMAN_ONLY)
def test_a01_each_human_only_operation_denies_the_agent(method: str, path: str) -> None:
    # Absent is deny in `authorise` (no `allow` among the decisions); never task_scope or allow.
    assert RULES[_action(method, path)].decisions.get("agent") in (None, "deny")


@pytest.mark.parametrize(
    ("method", "path"),
    [("get", BINDER), ("get", f"{BINDER}/requests"), ("get", f"{BINDER}/live")],
)
def test_a01_the_agent_reads_binders_only_inside_its_task(method: str, path: str) -> None:
    assert RULES[_action(method, path)].decisions.get("agent") == "task_scope"
