"""P-11-T04: the C11 consumer suite (SPEC-520 AC-32, AC-28; `docs/contracts/c11-renderer.md`).
Written from the contract and SPEC-520 for the consumers (ENG-04, AUD-21…23, NOT-03, TAX-12,
CLS-08, FSP-06, F-06's T10 and F-07's field manifest), not from the implementation: the shapes
they read, the refusal codes they branch on (`missing_variable`, `final_requires_approval`,
`document_locked`), the human-only actions and the audit event names. It runs in the provider's
CI (the contracts shard) and must stay green through every later P-11 change."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import cast, get_args

import pytest

from abacus.api.export_openapi import document
from abacus.modules.identity.authz.matrix import RULES
from abacus.modules.reporting import contract as c11

Json = dict[str, object]
SCHEMAS = cast(
    dict[str, Json],
    cast(dict[str, Json], cast(Json, json.loads(document()))["components"])["schemas"],
)
CONTRACT = (Path(__file__).resolve().parents[4] / "docs/contracts/c11-renderer.md").read_text(
    encoding="utf-8"
)


def _schema(name: str) -> Json:
    return SCHEMAS[name]


def _required(name: str) -> set[str]:
    return set(cast(list[str], _schema(name).get("required", [])))


def _section(number: int) -> str:
    match = re.search(rf"^## {number}\. .*?$(.*?)(?=^## |\Z)", CONTRACT, re.M | re.S)
    assert match is not None, f"contract section {number}"
    return match.group(1)


# --- Shapes the consumers read ---------------------------------------------------------------


def test_ac32_generated_document_carries_status_versions_and_allowed_actions() -> None:
    assert {
        "id",
        "kind",
        "owner_ref",
        "status",
        "out_of_date",
        "out_of_date_reasons",
        "current_version",
        "versions",
        "allowed_actions",
    } <= _required("GeneratedDocumentOut")
    assert {
        "n",
        "mode",
        "files",
        "content_hash",
        "template",
        "snapshot_sha256",
        "engine_version",
        "requested_by",
        "approval",
        "created_at",
    } <= _required("GeneratedVersionOut")
    assert {"format", "evidence_version_id", "render_hash", "page_count"} <= _required(
        "GeneratedFileOut"
    )


def test_ac32_status_words_are_df31s() -> None:
    status = _schema("GeneratedDocumentStatus")
    assert set(cast(list[str], status["enum"])) == {"drafting", "draft", "approved", "locked"}


def test_ac32_f07_and_fsp06_field_manifest_is_satisfiable() -> None:
    assert {"field_key", "label", "page", "rect_pt", "value_text", "match_id"} <= _required(
        "FieldRegionOut"
    )
    rect = cast(Json, cast(Json, _schema("FieldRegionOut")["properties"])["rect_pt"])
    assert (rect.get("minItems"), rect.get("maxItems")) == (4, 4)


def test_ac32_docblocks_are_the_closed_vocabulary_of_the_contract() -> None:
    names = {
        model.model_fields["type"].default
        for model in (
            c11.SectionBlock,
            c11.HeadingBlock,
            c11.ParagraphBlock,
            c11.ClauseBlock,
            c11.ListBlock,
            c11.TableBlock,
            c11.KvBlock,
            c11.SignatureBlock,
            c11.LegendBlock,
            c11.ImageBlock,
            c11.EnclosuresBlock,
            c11.PageBreakBlock,
        )
    }
    assert names == {
        "section",
        "heading",
        "paragraph",
        "clause",
        "list",
        "table",
        "kv",
        "signature_block",
        "legend",
        "image",
        "enclosures",
        "page_break",
    }
    for name in sorted(names):
        assert f"`{name}" in _section(6), name
    runs = {m.model_fields["type"].default for m in (c11.TextRun, c11.VarRun, c11.CiteRun)}
    assert runs == {"text", "var", "cite"}


def test_ac32_table_cells_are_strings_the_renderer_never_sums() -> None:
    rows = cast(Json, cast(Json, _schema("TableBlock")["properties"])["rows"])
    cell = cast(Json, cast(Json, rows["items"])["items"])
    assert cell["type"] == "string"


def test_ac32_an_image_is_an_asset_id_never_a_url() -> None:
    props = cast(Json, _schema("ImageBlock")["properties"])
    assert set(props) == {"type", "asset_id"}


# --- Refusal codes -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "code", ["missing_variable", "final_requires_approval", "document_locked"]
)
def test_ac32_the_refusal_codes_consumers_branch_on(code: str) -> None:
    assert code in get_args(c11.C11ErrorCode)
    assert f"`{code}" in _section(7)


def test_ac32_every_contract_error_code_is_in_the_shape() -> None:
    named = set(re.findall(r"`([a-z_]+)(?:\{[a-z]+\})?`", _section(7)))
    assert named <= set(get_args(c11.C11ErrorCode))


def test_ac32_regenerate_and_publish_answer_409() -> None:
    doc = cast(Json, json.loads(document()))
    paths = cast(dict[str, dict[str, Json]], doc["paths"])
    for path in (
        "/v1/generated-documents/{document_id}/regenerate",
        "/v1/report-templates/{template_id}/versions/{version_no}/publish",
    ):
        assert "409" in cast(Json, paths[path]["post"]["responses"]), path


# --- Human-only actions and audit names ---------------------------------------------------------


@pytest.mark.parametrize("action", c11.HUMAN_ONLY_ACTIONS)
def test_ac32_human_only_actions_deny_the_agent_and_the_system(action: str) -> None:
    rule = RULES[action]
    assert rule.decisions.get("agent") == "deny", action
    assert rule.decisions.get("system") == "deny", action
    assert f"`{action}`" in _section(4)


def test_ac32_the_audit_event_names_are_the_contracts() -> None:
    named = set(re.findall(r"`([a-z_]+\.[a-z_]+)`", _section(5)))
    assert named == set(c11.AUDIT_EVENTS)
