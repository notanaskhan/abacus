"""C5 section `portal-pbc` consumer tests (R-01-T02), on behalf of R-01 (POR-03, POR-04, POR-14),
T-02 (POR-05 falls back to POR-04's upload), C-01 (POR-11 reuses the rows and the POR-04 question
slot) and A-09 (POR-23 reuses the room). What they rely on: a portal answer carries client words
only (To do · Done · Ignored · Returned), one receipt-kind and one `allowed_actions` vocabulary,
a room that is only the caller's delegated items, and never a firm status code, an amount, a
confidence, a screening verdict or an agent reference anywhere in a response. Schema, matrix and
documents only: the routes are stubs. The TypeScript half is
`apps/web/src/fixtures/contracts/portal-pbc.contract.test.ts`."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import cast

import pytest
import yaml

from abacus.api.export_openapi import document
from abacus.kernel import _statuses
from abacus.modules.identity.authz.matrix import RULES

Json = dict[str, object]
REPO = Path(__file__).resolve().parents[4]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
SCHEMAS = cast(dict[str, Json], cast(Json, DOC["components"])["schemas"])
VOCABULARY = cast(
    dict[str, dict[str, object]],
    yaml.safe_load((REPO / "docs/product/status-vocabulary.yaml").read_text())["objects"],
)
CONTRACT = (REPO / "docs/contracts/portal-pbc.md").read_text()
STATUS_ENUMS = {
    name for name, value in vars(_statuses).items() if isinstance(value, type) and name[0] != "_"
}
FIRM_ROLES = {
    "firm_admin",
    "practice_leader",
    "quality_partner",
    "security_admin",
    "firm_partner",
    "engagement_partner",
    "manager",
    "senior",
    "staff",
    "reviewer",
    "eqr_reviewer",
    "specialist",
    "client_service",
}

# Every answer a portal person reads (method, path) -> the 2xx response schema's name.
PORTAL_READS: dict[tuple[str, str], str] = {
    ("get", "/v1/portal/binders"): "PortalBinderListOut",
    ("get", "/v1/portal/binders/{binder_id}"): "PortalBinderOut",
    ("get", "/v1/portal/request-items/{item_id}"): "PortalRequestOut",
    ("get", "/v1/portal/room"): "PortalRoomOut",
    ("post", "/v1/portal/room/suggest"): "RoomSuggestOut",
    ("get", "/v1/portal/drops/{batch_id}"): "DropBatchOut",
    ("post", "/v1/portal/request-items/{item_id}/ignore/undo"): "IgnoreUndoneOut",
    ("post", "/v1/portal/binders/{binder_id}/mark-done/undo"): "MarkDoneUndoneOut",
    ("post", "/v1/portal/binders/{binder_id}/drops"): "DropAcceptedOut",
}
CLIENT_WORDS = {"to_do", "done", "ignored", "returned"}
RECEIPT_KINDS = {
    "uploaded",
    "uploaded_by_other_contact",
    "emailed",
    "rule_linked_pending",
    "received",
}
ALLOWED_ACTIONS = {
    "upload",
    "ignore",
    "undo_ignore",
    "withdraw",
    "mark_done",
    "undo_mark_done",
    "comment",
}
DROP_OUTCOMES = {"rule_linked", "waiting", "duplicate_flagged", "refused"}
# A field name that would carry a firm status, an amount or an agent reference (POR-03, POR-04
# and POR-14 AVOID lists; contract §1). `client_status` is the client's words, checked below.
FORBIDDEN = re.compile(
    r"^(status|.+_status|amount|.+_amount|balance|materiality|currency|.*confidence.*|.*score.*|"
    r"screening.*|verdict|agent|agent_.+|.+_agent|run_id|.+_run_id|suggested_by|proposed_by)$"
)
ALLOWED_STATUS_FIELDS = {"client_status"}


def _schema_tree(name: str) -> dict[str, Json]:
    """`name` and every component schema it reaches, by name."""
    seen: dict[str, Json] = {}

    def walk(node: object) -> None:
        if isinstance(node, dict):
            ref = cast(Json, node).get("$ref")
            if isinstance(ref, str):
                target = ref.rsplit("/", 1)[1]
                if target not in seen:
                    seen[target] = SCHEMAS[target]
                    walk(SCHEMAS[target])
            for value in cast(Json, node).values():
                walk(value)
        elif isinstance(node, list):
            for value in cast(list[object], node):
                walk(value)

    seen[name] = SCHEMAS[name]
    walk(SCHEMAS[name])
    return seen


def leaks(tree: dict[str, Json]) -> list[str]:
    """Each field in the tree that carries a firm status code, an amount or an agent reference:
    by its name, or by reaching a status-registry enum (the firm's codes)."""
    found: list[str] = []
    for schema_name, schema in tree.items():
        if schema_name in STATUS_ENUMS:
            found.append(f"{schema_name} (a firm status enum)")
        props = cast(dict[str, Json], schema.get("properties", {}))
        for field in props:
            if field in ALLOWED_STATUS_FIELDS:
                continue
            if FORBIDDEN.match(field):
                found.append(f"{schema_name}.{field}")
    return found


def _enum(schema_name: str, field: str) -> set[str]:
    """The values a field may take, through `$ref`, `anyOf` (nullable) and array `items`."""
    node = cast(dict[str, Json], SCHEMAS[schema_name]["properties"])[field]

    def values(n: Json) -> set[str]:
        if "$ref" in n:
            return values(SCHEMAS[cast(str, n["$ref"]).rsplit("/", 1)[1]])
        if "enum" in n:
            return set(cast(list[str], n["enum"]))
        if "const" in n:
            return {cast(str, n["const"])}
        out: set[str] = set()
        for key in ("anyOf", "oneOf"):
            for option in cast(list[Json], n.get(key, [])):
                out |= values(option)
        if "items" in n:
            out |= values(cast(Json, n["items"]))
        return out

    return values(node)


def _response(method: str, path: str) -> str:
    responses = cast(dict[str, Json], PATHS[path][method]["responses"])
    ok = next(code for code in responses if code.startswith("2"))
    content = cast(dict[str, Json], responses[ok]["content"])
    schema = cast(Json, content["application/json"]["schema"])
    return cast(str, schema["$ref"]).rsplit("/", 1)[1]


@pytest.mark.parametrize(("method", "path"), sorted(PORTAL_READS))
def test_each_portal_answer_is_the_contract_model(method: str, path: str) -> None:
    assert _response(method, path) == PORTAL_READS[(method, path)]


@pytest.mark.parametrize(("method", "path"), sorted(PORTAL_READS))
def test_no_portal_answer_carries_a_firm_status_an_amount_or_an_agent(
    method: str, path: str
) -> None:
    assert leaks(_schema_tree(PORTAL_READS[(method, path)])) == []


def test_the_leak_check_would_fail_on_a_planted_firm_field() -> None:
    planted: dict[str, Json] = {
        "PlantedRowOut": {
            "properties": {
                "status": {"type": "string"},
                "amount": {"type": "string"},
                "agent_name": {"type": "string"},
                "match_confidence": {"type": "number"},
                "client_status": {"type": "string"},
            }
        },
        "RequestStatus": {"enum": ["requested", "uploaded"]},
    }
    assert sorted(leaks(planted)) == [
        "PlantedRowOut.agent_name",
        "PlantedRowOut.amount",
        "PlantedRowOut.match_confidence",
        "PlantedRowOut.status",
        "RequestStatus (a firm status enum)",
    ]


def test_client_words_are_the_registry_client_labels() -> None:
    labels = {
        str(code["client_label"]).lower().replace(" ", "_")
        for code in cast(dict[str, Json], VOCABULARY["request"]["codes"]).values()
        if "client_label" in code
    }
    assert labels == CLIENT_WORDS
    for schema_name in ("PortalRowOut", "PortalRequestOut", "IgnoreUndoneOut"):
        assert _enum(schema_name, "client_status") == CLIENT_WORDS, schema_name


def test_receipts_have_one_kind_vocabulary() -> None:
    assert _enum("PortalReceiptOut", "kind") == RECEIPT_KINDS
    for kind in RECEIPT_KINDS:
        assert f"`{kind}`" in CONTRACT, kind


@pytest.mark.parametrize(
    "schema_name",
    ["PortalBinderOut", "PortalRowOut", "PortalRequestOut", "PortalRoomRowOut"],
)
def test_allowed_actions_use_the_one_vocabulary(schema_name: str) -> None:
    assert _enum(schema_name, "allowed_actions") == ALLOWED_ACTIONS
    for action in ALLOWED_ACTIONS:
        assert f"`{action}`" in CONTRACT, action


def test_the_room_is_only_delegated_items() -> None:
    """A third party's room names no binder, category, other party or client-wide count; a row is
    an item and its own files, guidance and thread (the `delegated_only` shape)."""
    room = set(cast(dict[str, Json], SCHEMAS["PortalRoomOut"]["properties"]))
    assert room == {
        "engagement_label",
        "firm_name",
        "organisation_name",
        "intro",
        "uploaded_count",
        "total",
        "complete",
        "bands",
    }
    row = set(cast(dict[str, Json], SCHEMAS["PortalRoomRowOut"]["properties"]))
    assert not row & {"binder_id", "category", "other_parties", "open_count", "client_status"}
    tree = _schema_tree("PortalRoomOut")
    assert not {"PortalBinderOut", "PortalCategoryOut", "PortalGroupOut"} & set(tree)


def test_the_suggest_sees_file_names_only() -> None:
    assert set(cast(dict[str, Json], SCHEMAS["RoomSuggestIn"]["properties"])) == {"file_names"}


def test_a_drop_outcome_is_one_of_four_and_a_refusal_names_its_code() -> None:
    assert _enum("DropFileOut", "outcome") == DROP_OUTCOMES
    assert _enum("DropFileOut", "refusal") == {"file_too_large", "type_not_allowed"}


def test_the_other_parties_note_is_organisation_names_only() -> None:
    prop = cast(dict[str, Json], SCHEMAS["PortalBinderOut"]["properties"])["other_parties"]
    assert cast(Json, prop["items"])["type"] == "string"


def test_the_sheet_variant_slots_are_typed_for_c01_and_t06() -> None:
    assert _enum("PortalRequestOut", "variant") == {"request", "question", "decision"}


def test_the_read_grants_no_firm_role_and_the_agent_nothing() -> None:
    rule = RULES["portal_documents.read"]
    assert not {r for r, d in rule.decisions.items() if d != "deny"} & FIRM_ROLES
    assert rule.decisions.get("agent") == "deny"
    assert rule.scope_only


def test_the_contract_names_every_human_only_action_and_audit_event() -> None:
    human_only = CONTRACT.split("## 5. Human-only actions")[1].split("## 6.")[0]
    for action in ("Accept", "Return", "Void"):
        assert f"**{action}**" in human_only, action
    for event in (
        "request_item.ignore_undone",
        "binder.mark_done_undone",
        "portal.drop_received",
        "portal.drop.sorted",
        "fulfilment.created",
        "evidence_version.duplicate_flagged",
        "fulfilment.voided",
        "client_invitation.created",
    ):
        assert f"`{event}`" in CONTRACT, event


def test_the_contract_names_its_consumers_and_error_codes() -> None:
    header = CONTRACT.split("## 1.")[0]
    for consumer in ("R-01", "T-02", "C-01", "A-09"):
        assert consumer in header, consumer
    for code in ("firm_already_acted", "not_voidable", "file_too_large", "type_not_allowed"):
        assert f'"{code}"' in CONTRACT, code
    assert "`consent_required`" in CONTRACT
