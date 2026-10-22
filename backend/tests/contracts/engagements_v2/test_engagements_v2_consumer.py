"""Engagements v2 consumer contract tests (P-07-T06; SPEC-321 AC-23 to AC-25): what ENG-01, ENG-02
and ENG-03 rely on, read from the OpenAPI document. F-02-T11's C1 check is reused for the
excluded-type list and the C1 enum, and extended to the catalogue and the create refusal.

- the index is the P-36 envelope whose tiles are the engagement registry's codes and whose
  segments are the four service lines, plus the summary line;
- the record and gates carry what the rail and gate rows need;
- `single_audit` is absent from GET /v1/engagement-types, and a draft or create naming it is the
  server's 422 `unknown_engagement_type` (a code string, not a closed enum the schema refuses).
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import cast

import yaml

from abacus.api.export_openapi import document

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
SCHEMAS = cast(dict[str, Json], cast(Json, DOC["components"])["schemas"])
REPO = Path(__file__).resolve().parents[4]
VOCABULARY = REPO / "docs" / "product" / "status-vocabulary.yaml"
OBJECTS = cast(dict[str, Json], yaml.safe_load(VOCABULARY.read_text())["objects"])
ERROR_CODES = REPO / "docs" / "architecture" / "error-codes.yaml"
DRAFTS = "/v1/engagement-drafts"


def _f02_t11() -> ModuleType:
    """F-02-T11's C1 consumer module, loaded by path (tests are not a package here)."""
    path = Path(__file__).resolve().parents[1] / "c1_work_items" / "test_c1_consumer.py"
    spec = importlib.util.spec_from_file_location("c1_consumer_f02_t11", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


C1 = _f02_t11()
EXCLUDED = cast(set[str], C1.EXCLUDED)


def _props(schema: str) -> dict[str, Json]:
    return cast(dict[str, Json], SCHEMAS[schema].get("properties", {}))


def _codes(obj: str) -> set[str]:
    return set(cast(dict[str, object], OBJECTS[obj]["codes"]))


# --- ENG-01 -------------------------------------------------------------------------------------


def test_ac23_the_index_is_the_envelope_with_tiles_segments_and_a_summary() -> None:
    page = _props("EngagementIndexPage")
    assert {"items", "next_cursor", "total", "counts", "facets", "summary"} <= set(page)
    assert set(_props("EngagementIndexSummaryOut")) == {"prospect", "awaiting_letter", "past_due"}
    params = cast(list[Json], PATHS["/v1/engagements/index"]["get"]["parameters"])
    by_name = {cast(str, p["name"]): p for p in params}
    assert {"service_line", "status", "tile", "letter", "next_due", "period", "client_id"} <= set(
        by_name
    )


def test_ac23_tiles_are_the_engagement_registry_codes() -> None:
    assert set(cast(list[str], SCHEMAS["EngagementStatus"]["enum"])) == _codes("engagement")
    assert set(cast(list[str], SCHEMAS["LetterRecordStatus"]["enum"])) == _codes("letter_record")
    row = _props("EngagementIndexRowOut")
    assert row["status"]["$ref"] == "#/components/schemas/EngagementStatus"
    assert set(cast(list[str], row["service_line"]["enum"])) == {"audit", "tax", "cas", "advisory"}


def test_ac23_the_row_carries_eng01s_columns() -> None:
    assert {
        "name",
        "client_name",
        "type",
        "period_label",
        "office_name",
        "partner_initials",
        "status",
        "work_items",
        "letter",
        "next_due",
        "allowed_actions",
    } <= set(_props("EngagementIndexRowOut"))
    assert {"status", "signed_on", "last_event", "signed_count", "signer_count"} <= set(
        _props("EngagementLetterSummaryOut")
    )


# --- ENG-02 -------------------------------------------------------------------------------------


def test_ac24_the_record_carries_rail_bands_contacts_gates_and_read_only_reason() -> None:
    record = _props("EngagementRecordOut")
    assert {"bands", "contacts", "letter", "gates", "tab_counts", "read_only_reason"} <= set(
        record
    )
    options = cast(list[Json], record["read_only_reason"]["anyOf"])
    assert {"type": "string", "const": "archived"} in options or {
        "type": "string",
        "enum": ["archived"],
    } in options
    bands = cast(list[str], _props("EngagementRailBandOut")["band"]["enum"])
    assert set(bands) == {"details", "review_delivery", "client_portal"}


def test_ac24_gates_are_g1_to_g9_with_object_ref_blockers() -> None:
    gate = _props("EngagementGateOut")
    assert set(cast(list[str], gate["gate"]["enum"])) == {f"G{n}" for n in range(1, 10)}
    assert {"type", "id", "reason_code"} == set(_props("GateBlockerRefOut"))
    ok = cast(Json, PATHS["/v1/engagements/{engagement_id}/gates"]["get"]["responses"])["200"]
    schema = cast(Json, cast(Json, cast(Json, ok)["content"])["application/json"])["schema"]
    assert cast(Json, schema)["items"] == {"$ref": "#/components/schemas/EngagementGateOut"}


# --- ENG-03: no single_audit, refused with 422 unknown_engagement_type --------------------------


def test_ac25_f02_t11_still_holds_for_c1() -> None:
    C1.test_c1_the_engagement_type_holds_the_14_types_and_no_excluded_one()


def test_ac25_single_audit_is_absent_from_the_catalogue() -> None:
    entry = _props("EngagementTypeEntryOut")
    codes = set(cast(list[str], entry["code"]["enum"]))
    assert "single_audit" not in codes and not codes & EXCLUDED
    assert len(codes) == 18  # Tax 8 · Audit & assurance 8 · CAS & Advisory 2
    assert not set(cast(list[str], entry["engagement_type"]["enum"])) & EXCLUDED
    draft_code = cast(list[Json], _props("EngagementDraftOut")["type_code"]["anyOf"])
    assert {"$ref": "#/components/schemas/CatalogueTypeCode"} not in draft_code
    assert not [o for o in draft_code if "single_audit" in json.dumps(o)]


def test_ac25_a_single_audit_draft_is_the_servers_422_unknown_engagement_type() -> None:
    # The draft takes a code string (not a closed enum), so the refusal is the catalogue's code.
    type_code = cast(list[Json], _props("EngagementDraftIn")["type_code"]["anyOf"])
    assert {"type": "string", "pattern": "^[a-z0-9_]{1,40}$"} in type_code
    codes = cast(dict[str, Json], yaml.safe_load(ERROR_CODES.read_text())["codes"])
    assert codes["unknown_engagement_type"]["status"] == 422
    for path in (DRAFTS, f"{DRAFTS}/{{draft_id}}/create"):
        assert "422" in cast(Json, PATHS[path]["post"]["responses"])


def test_ac25_create_answers_409_for_duplicates_and_unmet_g1() -> None:
    responses = cast(Json, PATHS[f"{DRAFTS}/{{draft_id}}/create"]["post"]["responses"])
    assert {"201", "409", "422"} <= set(responses)
    assert "confirm_duplicate" in _props("DraftCreateIn")
