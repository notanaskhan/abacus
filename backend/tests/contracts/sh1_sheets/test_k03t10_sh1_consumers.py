"""SH-1 v1 consumer tests (K-03-T10; TASK-8854; SPEC-721; C23; DEC-5851): each operation under its
one matrix action with its 501, every write denied to the agent and the system, and the SheetVM
fields SHT-01, SHT-02 and SHT-04 read. The fixture half is
`apps/web/src/fixtures/contracts/sh1-sheets.contract.test.ts`."""

from __future__ import annotations

import json
from typing import cast

import pytest

from abacus.api.export_openapi import document
from abacus.modules.identity.authz.matrix import RULES
from abacus.modules.workpapers.sheets_contract import (
    AgentColumnOut,
    SheetCellOut,
    SheetColumnOut,
    SheetRowOut,
    SheetStatusOut,
    SheetVmOut,
)

Json = dict[str, object]
PATHS = cast(dict[str, dict[str, Json]], json.loads(document())["paths"])
S = "/v1/sheets/{sheet_id}"
A = f"{S}/columns/{{column_id}}/agent"
OPERATIONS = {
    ("post", "/v1/work-items/{work_item_id}/sheets"): "sheet.configure",
    ("get", S): "sheet.read",
    ("get", f"{S}/rows"): "sheet.read",
    ("post", f"{S}/rows/from-sample"): "sheet.edit",
    ("post", f"{S}/rows"): "sheet.edit",
    ("patch", f"{S}/rows/{{row_id}}"): "sheet.edit",
    ("get", f"{S}/views"): "sheet.read",
    ("post", f"{S}/views"): "sheet.edit",
    ("patch", f"{S}/views/{{view_id}}"): "sheet.edit",
    ("post", f"{S}/columns"): "sheet.configure",
    ("patch", f"{S}/columns/{{column_id}}"): "sheet.configure",
    ("get", f"{S}/columns/{{column_id}}/usage"): "sheet.read",
    ("delete", f"{S}/columns/{{column_id}}"): "sheet.configure",
    ("get", A): "sheet.read",
    ("put", A): "sheet.configure",
    ("post", f"{A}/preview"): "agent_column.run",
    ("post", f"{A}/estimate"): "agent_column.run",
    ("post", f"{A}/runs"): "agent_column.run",
    ("post", f"{A}/runs/{{run_id}}/stop"): "agent_column.run",
    ("get", f"{S}/export.xlsx"): "sheet.export",
}


@pytest.mark.parametrize(("op", "action"), sorted(OPERATIONS.items()), ids=str)
def test_every_operation_is_declared_with_its_action_and_501(
    op: tuple[str, str], action: str
) -> None:
    method, path = op
    operation = PATHS[path][method]
    assert operation["x-abacus-action"] == action
    assert "501" in cast(Json, operation["responses"])


@pytest.mark.parametrize(
    "action", ["sheet.edit", "sheet.configure", "agent_column.run", "sheet.export"]
)
def test_every_write_is_denied_to_the_agent_and_the_system(action: str) -> None:
    rule = RULES[action]
    assert rule.decisions.get("agent") == "deny" and rule.decisions.get("system") == "deny"


@pytest.mark.parametrize(
    ("model", "fields"),
    [
        (SheetVmOut, {"columns", "sections", "status", "signed_off", "allowed_actions"}),
        (SheetColumnOut, {"key", "type", "label", "width", "frozen", "agent_name", "options"}),
        (SheetRowOut, {"key", "section_key", "locked", "version", "cells"}),
        (SheetCellOut, {"value", "state", "raw", "was", "citation_ids", "exception"}),
        (SheetStatusOut, {"rows", "exceptions", "view", "agent_running", "agent_summary"}),
        (
            AgentColumnOut,
            {"instruction", "mention_refs", "output_type", "options", "status", "saved_by"},
        ),
    ],
    ids=lambda v: getattr(v, "__name__", ""),
)
def test_the_sheet_vm_fields_are_present(model: type, fields: set[str]) -> None:
    assert fields <= set(model.model_fields)  # type: ignore[attr-defined] -- a pydantic model
