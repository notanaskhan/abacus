"""Audits family consumer tests (A-01-T03; SPEC-330 AC-8), for AUD-01, AUD-02 and AUD-03 and the
C5 v1.1 additive request-row fields. Schema and matrix only: the routes are stubs
(`test_audits_stub.py`); the envelope's footing and counts minus the active tile are asserted on
the fixtures in `apps/web/src/fixtures/contracts/audits.contract.test.ts`."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import cast

import pytest
import yaml

from abacus.api.export_openapi import document

Json = dict[str, object]
REPO = Path(__file__).resolve().parents[4]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
SCHEMAS = cast(dict[str, Json], cast(Json, DOC["components"])["schemas"])
REGISTRY = cast(
    dict[str, dict[str, dict[str, object]]],
    yaml.safe_load((REPO / "docs/product/status-vocabulary.yaml").read_text())["objects"],
)
ITEM = "/v1/audits/{work_item_id}"
ROOTS = (
    "AuditIndexPage",
    "AuditCockpitOut",
    "AuditProfileOut",
    "AuditPhaseOut",
    "ReleaseRecordOut",
    "ArchiveRecordOut",
    "SourceDocumentsOut",
)
# A hidden count, an amount, materiality or a severity (INV-3, DEC-43; AUD-01 AVOID).
FORBIDDEN = re.compile(r"hidden|walled|amount|materiality|severity|balance")


def _codes(obj: str) -> set[str]:
    """The object's stored codes: a derived word (`processing`, `overdue`) is never a field value
    (the run badge and the `overdue` flag carry them)."""
    codes = cast(dict[str, dict[str, object]], REGISTRY[obj]["codes"])
    return {c for c, entry in codes.items() if entry.get("derived") is not True}


def _props(model: str) -> dict[str, Json]:
    return cast(dict[str, Json], SCHEMAS[model]["properties"])


def _options(prop: Json) -> list[Json]:
    if "anyOf" in prop:
        return cast(list[Json], prop["anyOf"])
    if prop.get("type") == "array":
        return [cast(Json, prop["items"])]
    return [prop]


def _enum(prop: Json) -> set[str]:
    out: set[str] = set()
    for option in _options(prop):
        target = (
            SCHEMAS[cast(str, option["$ref"]).rsplit("/", 1)[1]] if "$ref" in option else option
        )
        out |= {str(v) for v in cast(list[object], target.get("enum", []))}
    return out


def _walk(model: str, seen: set[str] | None = None) -> Iterator[tuple[str, str]]:
    """Every (model, field) reachable from `model` through `$ref`s."""
    seen = set() if seen is None else seen
    if model in seen:
        return
    seen.add(model)
    for name, prop in cast(dict[str, Json], SCHEMAS[model].get("properties", {})).items():
        yield model, name
        for option in _options(prop):
            ref = option.get("$ref")
            if ref is None and option.get("type") == "array":
                ref = cast(Json, option["items"]).get("$ref")
            if isinstance(ref, str):
                target = ref.rsplit("/", 1)[1]
                if "properties" in SCHEMAS[target]:
                    yield from _walk(target, seen)


def _query(method: str, path: str, name: str) -> Json:
    params = cast(list[Json], PATHS[path][method].get("parameters", []))
    return cast(Json, next(p for p in params if p["name"] == name)["schema"])


@pytest.mark.parametrize("root", ROOTS)
def test_ac8_no_field_reveals_a_hidden_count_or_an_amount(root: str) -> None:
    bad = [f"{m}.{f}" for m, f in _walk(root) if FORBIDDEN.search(f)]
    assert bad == []


def test_ac8_the_index_is_the_p36_envelope_with_its_caption() -> None:
    props = _props("AuditIndexPage")
    assert {"items", "next_cursor", "total", "counts", "facets", "summary"} <= set(props)
    assert set(_props("AuditIndexSummaryOut")) == {
        "ebp",
        "fs_audit",
        "review",
        "compilation_preparation",
        "soc",
        "internal_audit",
    }


@pytest.mark.parametrize(
    ("model", "field", "obj"),
    [
        ("AuditIndexRowOut", "phase", "audit_engagement"),
        ("AuditOverviewOut", "phase", "audit_engagement"),
        ("AuditPhaseIn", "to", "audit_engagement"),
        ("AuditPhaseOut", "from_phase", "audit_engagement"),
        ("AuditPhaseOut", "to_phase", "audit_engagement"),
        ("AuditSectionRowOut", "section_state", "audit_section"),
        ("SourceDocumentRowOut", "status", "request"),
        ("SourceDocumentRowOut", "screening", "evidence_screening"),
    ],
)
def test_ac8_status_fields_are_exactly_the_registry_codes(
    model: str, field: str, obj: str
) -> None:
    assert _enum(_props(model)[field]) == _codes(obj)


def test_ac8_the_archive_cell_uses_the_registry_archive_words() -> None:
    assert _enum(_props("AuditArchiveOut")["state"]) == {"archiving", "archived"}
    assert {"archiving", "archived"} <= _codes("audit_engagement")


def test_ac8_the_phase_tile_filter_takes_registry_codes() -> None:
    assert _enum(_query("get", "/v1/audits", "phase")) == _codes("audit_engagement")
    assert _enum(_query("get", "/v1/audits", "due")) == {"any", "7d", "14d", "30d"}
    assert _enum(_query("get", "/v1/audits", "segment")) == {"fs", "ebp", "review", "soc", "ia"}


def test_ac8_no_audit_type_is_single_audit() -> None:
    types = _enum(_props("AuditIndexRowOut")["engagement_type"])
    assert "single_audit" not in types
    assert {"ebp_audit", "fs_audit", "review", "compilation", "preparation"} <= types


def test_ac8_the_ebp_plan_kinds_hold_no_health_and_welfare_plan() -> None:
    for model in ("AuditIndexRowOut", "AuditProfileIn", "AuditProfileOut"):
        assert _enum(_props(model)["ebp_plan_kind"]) == {"dc", "403b", "db"}


def test_ac8_tags_say_whether_metadata_only_roles_may_see_them() -> None:
    assert _enum(_props("AuditIndexTagOut")["classification"]) == {"metadata", "content"}


def test_ac8_rail_rows_name_their_route_and_whether_it_is_built() -> None:
    props = _props("AuditSectionRowOut")
    assert {"key", "route", "link", "grammar", "work_item_ref"} <= set(props)
    assert _enum(props["link"]) == {"live", "planned"}
    assert _enum(props["grammar"]) == {"sub_line", "idle_pill", "link"}
    assert _enum(_props("AuditCockpitOut")["dock_tabs"]) == {"agent", "viewer"}


def test_ac8_the_c5_v1_1_request_row_fields_are_additive_and_optional() -> None:
    row = SCHEMAS["BinderRequestRowOut"]
    props = _props("BinderRequestRowOut")
    added = {"owed_by", "latest_upload", "match_confidence"}
    assert added <= set(props)
    assert not added & set(cast(list[str], row.get("required", [])))
    # The fields AUD-03 already reads from C5 v1 stay.
    assert {"requested_at", "overdue", "screening", "linked_count", "due_on"} <= set(props)
    assert _enum(_props("RequestOwedByOut")["kind"]) == {
        "client_contact",
        "third_party",
        "organisation",
    }
    assert set(_props("RequestLatestUploadOut")) == {
        "evidence_version_id",
        "path_label",
        "uploaded_on",
        "uploader_kind",
    }


def test_ac8_source_documents_foot_with_counted_bands() -> None:
    assert {"received", "total", "needs_review", "requested", "groups"} <= set(
        _props("SourceDocumentsOut")
    )
    assert "counted" in _props("SourceDocumentGroupOut")
    assert _enum(_query("get", f"{ITEM}/source-documents", "sort")) == {
        "missing_first",
        "received_first",
    }
