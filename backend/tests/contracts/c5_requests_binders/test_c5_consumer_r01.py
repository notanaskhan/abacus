"""C5 v1 consumer tests for R-01 (POR-03, POR-04, POR-14, POR-20; P-06-T02): the shapes a client
principal receives, draft invisibility to client principals, the client's words, the portal
actions (mark done, ignore with a reason, upload intents, withdraw) and the per-binder follow-up
cadence POR-20's scheduler reads. Schema, matrix and read filter only: the routes are stubs."""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import cast

import pytest
import yaml
from sqlalchemy import Boolean, column, table
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import UUID

from abacus.api.export_openapi import document
from abacus.kernel.db import TenantContext
from abacus.modules.identity.api import AuthContext
from abacus.modules.identity.authz import visible_items
from abacus.modules.identity.authz.matrix import RULES

Json = dict[str, object]
REPO = Path(__file__).resolve().parents[4]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
SCHEMAS = cast(dict[str, Json], cast(Json, DOC["components"])["schemas"])
REQUEST_CODES = cast(
    dict[str, dict[str, object]],
    yaml.safe_load((REPO / "docs/product/status-vocabulary.yaml").read_text())["objects"][
        "request"
    ]["codes"],
)
CATALOGUE = cast(
    dict[str, dict[str, object]],
    yaml.safe_load((REPO / "docs/architecture/error-codes.yaml").read_text())["codes"],
)
PORTAL = "/v1/portal"
WITHDRAW = "/v1/engagements/{engagement_id}/evidence-versions/{version_id}/withdraw"
CLIENT_ROLES = {"client_admin", "client_contributor"}


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
    return {
        cast(str, v)
        for o in _options(_props(model)[field])
        for v in cast(list[object], o.get("enum", []))
    }


def _fields_deep(model: str, seen: frozenset[str] = frozenset()) -> set[str]:
    """Every property name a client receives in `model`, through nested models."""
    names: set[str] = set()
    for name, prop in _props(model).items():
        names.add(name)
        nested = [prop, *_options(prop)]
        items = [cast(Json, p["items"]) for p in nested if "items" in p]
        for option in [*nested, *items]:
            ref = option.get("$ref")
            target = ref.rsplit("/", 1)[1] if isinstance(ref, str) else None
            if target and target not in seen and "properties" in SCHEMAS[target]:
                names |= _fields_deep(target, seen | {model})
    return names


def _response_model(method: str, path: str, status: str = "200") -> str:
    response = cast(Json, cast(Json, PATHS[path][method]["responses"])[status])
    schema = cast(Json, cast(Json, cast(Json, response["content"])["application/json"])["schema"])
    return cast(str, schema["$ref"]).rsplit("/", 1)[1]


# --- What a client principal receives -----------------------------------------------------------

# The portal projection and the portal answers (contract §3). R-01 renders nothing else.
CLIENT_SHAPES = {
    ("get", "/v1/binders/{binder_id}/client-preview"): "BinderClientPreviewOut",
    ("post", f"{PORTAL}/binders/{{binder_id}}/mark-done"): "BinderMarkedDoneOut",
    ("post", f"{PORTAL}/request-items/{{item_id}}/ignore"): "IgnoredOut",
    ("post", f"{PORTAL}/request-items/{{item_id}}/upload-intents"): "UploadIntentOut",
    ("post", WITHDRAW): "WithdrawalOut",
}
# Fields that exist only while a request is drafted, or only for the firm (INV-4, DV-11).
FIRM_ONLY = {
    "drafted_by_run_id",
    "drafted_wording_source",
    "client_visible",
    "sent_by",
    "na_by",
    "na_reason",
    "firm_owner_user_id",
    "supports_ref",
    "linked_ref",
    "linked_count",
    "screening",
    "incorporation_state",
    "incorporated_by",
    "undo_until",
    "allowed_actions",
    "preparer_user_id",
    "published_by",
    "unpublished_by",
    "unpublish_reason",
    "template_ref",
    "prior_year_source_ref",
    "follow_up_override",
    "source_tag",
    "wave",
}


@pytest.mark.parametrize(("method", "path"), sorted(CLIENT_SHAPES))
def test_r01_each_client_route_answers_its_portal_shape(method: str, path: str) -> None:
    assert (
        _response_model(method, path, "201" if path.endswith("upload-intents") else "200")
        == (CLIENT_SHAPES[(method, path)])
    )


@pytest.mark.parametrize("model", sorted(set(CLIENT_SHAPES.values()) | {"ClientPreviewItemOut"}))
def test_r01_client_shapes_carry_no_draft_or_firm_only_field(model: str) -> None:
    assert not _fields_deep(model) & FIRM_ONLY


def test_r01_the_preview_item_is_the_client_wording_with_the_ignored_flag() -> None:
    assert _required("ClientPreviewItemOut") == {
        "id",
        "category_name",
        "title",
        "description",
        "status",
        "client_ignored",
    }
    assert _ref("ClientPreviewItemOut", "status") == "RequestStatus"
    assert _props("ClientPreviewItemOut")["client_ignored"]["type"] == "boolean"
    assert _required("BinderClientPreviewOut") == {"binder_id", "name", "status", "items"}
    assert {
        name for name, p in _props("ClientPreviewItemOut").items() if p["cls"] == "confidential"
    } == {"category_name", "title", "description"}


# --- Draft invisibility to client principals -----------------------------------------------------


def test_r01_a_draft_has_no_client_word() -> None:
    # Every request code a client can be shown has a client word; a draft has none (firm only).
    assert "client_label" not in REQUEST_CODES["draft"]
    assert "client_label" not in REQUEST_CODES["overdue"]  # derived; the client sees a date


@pytest.mark.parametrize("action", ["request_item.read", "binder.read", "evidence.read"])
def test_r01_client_roles_read_only_client_visible_or_assigned_rows(action: str) -> None:
    decisions = RULES[action].decisions
    assert {decisions[r] for r in CLIENT_ROLES} == {"client_visible_only", "assigned_only"}


@pytest.mark.parametrize("action", ["activity.read", "request_item.update", "binder.update"])
def test_r01_no_client_role_reaches_firm_only_reads_or_edits(action: str) -> None:
    assert not CLIENT_ROLES & set(RULES[action].decisions)


def _client_filter() -> str:
    user = uuid.uuid4()
    ctx = AuthContext(
        TenantContext(uuid.uuid4(), "human", str(user)), user, uuid.uuid4(), None, None
    )
    rows = table(
        "request_items",
        column("engagement_id", UUID),
        column("client_visible", Boolean),
        column("client_assignee_user_id", UUID),
        column("status"),
    )
    where = visible_items(
        ctx,
        "request_item.read",
        rows.c.engagement_id,
        rows.c.client_visible,
        rows.c.client_assignee_user_id,
    )
    return str(where.compile(dialect=postgresql.dialect()))


def test_r01_every_client_reach_of_the_request_filter_needs_client_visible() -> None:
    sql = _client_filter()
    grants = sql.count("FROM client_access_grants")
    assert grants == 2  # client admin and contributor
    assert sql.count("request_items.client_visible IS true") == grants


def test_r01_the_store_keeps_every_draft_off_the_client() -> None:
    # F-03-T15 (migration 0071): a request that is not client-visible is a draft and a
    # client-visible one is requested, so the client filter above never reaches a draft. The
    # latest migration that (re)defines the trigger function is the one in force.
    define = re.compile(
        r"CREATE (?:OR REPLACE )?FUNCTION request_item_requested\(\).*?\$\$(.*?)\$\$", re.S
    )
    bodies = [
        found.group(1)
        for path in sorted((REPO / "backend/migrations/versions").glob("*.py"))
        for found in define.finditer(path.read_text())
    ]
    assert bodies
    body = bodies[-1]
    assert "NEW.status := CASE WHEN NEW.client_visible THEN 'requested' ELSE 'draft' END" in body


@pytest.mark.xfail(
    strict=True,
    reason=(
        "TASK-420 finding (C5 §1, P-06 §4.3, SPEC-319 AC-6): publish 'sends draft client-visible "
        "requests', so a draft may be client-visible, but the client read filter checks "
        "client_visible only and the 0071 trigger forbids a client-visible draft; T10 must "
        "filter drafts by status when it allows one; see #282"
    ),
)
def test_r01_the_client_filter_excludes_drafts_by_status_too() -> None:
    assert "request_items.status" in _client_filter()


# --- The client's words (contract §4, DEC-09) ----------------------------------------------------

CLIENT_WORDS = {
    "requested": "To do",
    "uploaded": "Done",
    "received": "Done",
    "returned": "Returned",
    "not_applicable": "Ignored",
}


def test_r01_each_client_visible_code_reads_in_the_clients_words() -> None:
    words = {c: f["client_label"] for c, f in REQUEST_CODES.items() if "client_label" in f}
    assert words == CLIENT_WORDS
    assert set(words.values()) == {"To do", "Done", "Returned", "Ignored"}
    visible = set(cast(list[str], SCHEMAS["RequestStatus"]["enum"])) - {"draft"}
    assert visible == set(CLIENT_WORDS)


def test_r01_an_ignore_takes_spec_042_reasons_and_keeps_the_request_status() -> None:
    assert SCHEMAS["IgnoreIn"]["additionalProperties"] is False
    assert _required("IgnoreIn") == {"reason"}
    assert _enum("IgnoreIn", "reason") == {"not_this_year", "sent_another_way", "dont_have"}
    assert _enum("IgnoreIn", "reason") == _enum("ClientResponseIn", "reason")  # SPEC-042 codes
    assert _enum("BinderRequestRowOut", "client_ignore_reason") == _enum("IgnoreIn", "reason")
    assert _required("IgnoredOut") == {"request_item_id", "status", "client_ignored_at"}
    assert _ref("IgnoredOut", "status") == "RequestStatus"  # stays `requested` (OQ-3)
    assert RULES["request_item.ignore"].requires_reason


# --- The other portal actions -------------------------------------------------------------------


def test_r01_mark_done_returns_the_open_count_at_that_moment() -> None:
    assert _required("BinderMarkedDoneOut") == {
        "binder_id",
        "status",
        "marked_done_at",
        "open_count",
    }
    assert _ref("BinderMarkedDoneOut", "status") == "BinderStatus"
    assert _props("BinderMarkedDoneOut")["open_count"]["type"] == "integer"


def test_r01_upload_intents_announce_1_to_50_files_and_expire() -> None:
    files = _props("UploadIntentIn")["files_expected"]
    assert (files["minimum"], files["maximum"]) == (1, 50)
    assert SCHEMAS["UploadIntentIn"]["additionalProperties"] is False
    assert _required("UploadIntentOut") == {"request_item_id", "files_expected", "expires_at"}
    assert _props("UploadIntentOut")["expires_at"]["format"] == "date-time"


def test_r01_a_withdrawal_names_the_version_and_its_erase_date_never_the_file() -> None:
    assert set(_props("WithdrawalOut")) == {
        "evidence_version_id",
        "request_item_id",
        "withdrawn_at",
        "erase_after",
    }
    responses = set(cast(Json, PATHS[WITHDRAW]["post"]["responses"]))
    assert {"403", "409"} <= responses  # not_your_upload, evidence_accepted


def test_r01_the_follow_up_cadence_override_is_bounded_and_clearable() -> None:
    every = _props("FollowUpOverride")["every_days"]
    most = _props("FollowUpOverride")["max"]
    assert (every["minimum"], every["maximum"]) == (1, 30)
    assert (most["minimum"], most["maximum"]) == (1, 4)  # POR-20: at most 4
    assert _required("FollowUpOverrideIn") == {"override"}
    assert _ref("FollowUpOverrideIn", "override") == "FollowUpOverride"
    assert any(o.get("type") == "null" for o in _options(_props("FollowUpOverrideIn")["override"]))
    assert _ref("BinderOut", "follow_up_override") == "FollowUpOverride"


# --- Who may act (contract §2, §5) --------------------------------------------------------------

CLIENT_ACTS = [
    ("post", f"{PORTAL}/binders/{{binder_id}}/mark-done"),
    ("post", f"{PORTAL}/request-items/{{item_id}}/ignore"),
    ("post", f"{PORTAL}/request-items/{{item_id}}/upload-intents"),
    ("post", WITHDRAW),
]


@pytest.mark.parametrize(("method", "path"), CLIENT_ACTS)
def test_r01_the_agent_never_acts_for_the_client(method: str, path: str) -> None:
    action = cast(str, PATHS[path][method]["x-abacus-action"])
    assert RULES[action].decisions.get("agent") in (None, "deny")
    assert set(RULES[action].decisions) & CLIENT_ROLES


def test_r01_only_retrievals_upload_for_the_platform_and_nothing_withdraws_for_it() -> None:
    assert RULES["evidence.upload"].decisions.get("system") == "allow"
    assert RULES["evidence.withdraw"].decisions.get("system") == "deny"


# --- Error codes (contract §6) ------------------------------------------------------------------

CODES = {"reason_required": 422, "evidence_accepted": 409, "idempotency_key_reused": 422}


@pytest.mark.parametrize("code", sorted(CODES))
def test_r01_a_catalogued_code_keeps_the_contract_status(code: str) -> None:
    if code in CATALOGUE:
        assert CATALOGUE[code]["status"] == CODES[code]


def test_r01_not_your_upload_is_a_403_not_a_conflict() -> None:
    assert "not_your_upload" not in CATALOGUE  # the catalogue holds 409 and 422 codes only


@pytest.mark.xfail(
    strict=True,
    reason=(
        "TASK-420 finding (C5 §6, ADR-139): domain 422s answer "
        '{"detail": "reason_required"} (a code string, abacus.api.app._domain_invalid) but '
        "every 422 is documented as ValidationErrorOut, whose detail is a list of field errors; "
        "see #282"
    ),
)
def test_r01_the_documented_422_admits_a_domain_code() -> None:
    model = _response_model("post", f"{PORTAL}/request-items/{{item_id}}/ignore", "422")
    detail = [o.get("type") for o in _options(_props(model)["detail"])]
    assert "string" in detail
