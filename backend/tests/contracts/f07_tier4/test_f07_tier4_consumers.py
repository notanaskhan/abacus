"""F-07-T21 (TASK-7950; SPEC-652; F-07 §4.5): consumer contract tests for the tier-4 view models.

Written from the tier-4 templates' view models (T4 WB-01's thread, T13 the deadline calendar, T14
the relationship graph, T17 the rendered form) and the contracts they read, not from the
providers' code: each field a template reads must stay in the provider's published schema. They
run in the providers' CI (the contracts shard): C6 v2 (`agents`/`workbench`), C4 (`evidence`),
C11 (`reporting`), C21 (`organisations`/`practice` due-date rules). A provider renaming a field
a template reads fails here first.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from abacus.api.export_openapi import document

Json = dict[str, object]
SCHEMAS = cast(
    dict[str, Json],
    cast(dict[str, Json], cast(Json, json.loads(document()))["components"])["schemas"],
)
ROOT = Path(__file__).resolve().parents[4]


def _props(name: str) -> set[str]:
    return set(cast(dict[str, object], SCHEMAS[name].get("properties", {})))


# (template, provider schema, the fields the template's view model reads)
READS: list[tuple[str, str, set[str]]] = [
    # T4 · C6 v2: the thread, its items and the plan card (W-02-T17, T19, T21).
    ("T4", "SessionSnapshotOut", {"id", "title", "state", "items", "locked", "allowed_actions"}),
    ("T4", "SessionItemOut", {"id", "seq", "kind", "payload", "run_id", "step_id", "actor_kind"}),
    ("T4", "RunPlanOut", {"version", "state", "steps", "reads", "writes", "decided_by"}),
    # T17 · C4: the viewer's regions a traced field lights (manifest `match_id`).
    ("T17", "ViewerRegionOut", {"match_id", "page", "rects", "label"}),
    ("T17", "ViewerManifestOut", {"page_count", "pages", "pii_masks", "status"}),
    # T13 · C21: a deadline's original and extended due dates (the calendar's cells).
    ("T13", "DueDateOut", {"form", "tax_year", "original_due_on", "extended_due_on", "extension_form"}),
    # T14 · the relationship rows the graph's edges read (C12 lands with T-08; the client's own
    # relationships are read today).
    ("T14", "ClientRelationshipOut", {"id", "kind", "from_entity_id", "to_entity_id", "percent"}),
]


@pytest.mark.parametrize(("template", "schema", "fields"), READS)
def test_each_field_a_tier4_template_reads_is_published(
    template: str, schema: str, fields: set[str]
) -> None:
    assert schema in SCHEMAS, f"{template} reads {schema}, which the API no longer publishes"
    missing = fields - _props(schema)
    assert not missing, f"{template} reads {sorted(missing)} from {schema}"


def test_t4s_item_kinds_include_context_and_drill() -> None:
    """WB-01 and WB-03 read context and drill items; the snapshot must name them (I-02-T17)."""
    kind = cast(dict[str, object], cast(dict[str, object], SCHEMAS["SessionItemOut"]["properties"])["kind"])
    values = set(cast(list[str], kind.get("enum", [])))
    assert {"context_added", "context_removed", "drill", "question", "plan"} <= values


def test_t17s_manifest_regions_carry_the_servers_match_id() -> None:
    """INV-2: a traced field lights by the server's `match_id`, never one derived from text."""
    assert "match_id" in cast(list[str], SCHEMAS["ViewerRegionOut"].get("required", []))


@pytest.mark.parametrize("request_doc", ["t08-deadlines.md", "t08-relationships.md", "t06-form-pages.md"])
def test_the_three_contract_requests_list_states_and_seed_figures(request_doc: str) -> None:
    body = (ROOT / "docs/contracts/requests" / request_doc).read_text(encoding="utf-8")
    assert "## Screen states" in body and "## Seed figures" in body and "## Fields" in body
