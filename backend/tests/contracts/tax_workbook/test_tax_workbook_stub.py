"""T-05-T06 (TASK-6732; SPEC-651; T-05 §4.3): the tax workbook v1 stub's contract tests.

Row acceptance: "The stub merges dark behind tax.entity_workspace with generated client types, and
the contract doc lists every human-only action." The screens' fields exist on the models they read,
every route is published with its one action and a 501 until built, the human verbs deny the agent,
workbook values and memo text are tax return information, and the doc names every human verb."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest
import yaml
from pydantic import BaseModel

from abacus.api.export_openapi import document
from abacus.modules.tax import workbook_contract as wb

ROOT = Path(__file__).resolve().parents[4]
NEEDS: dict[str, tuple[type[BaseModel], tuple[str, ...]]] = {
    "TXP-00 run": (wb.WorkbookRunAcceptedOut, ("run_id", "run_no")),
    "TXP-01 memo": (wb.WorkbookMemoOut, ("status", "sections", "seen_hash", "stale_fields")),
    "TXP-02 TB": (
        wb.WorkbookTbRowOut,
        ("unadjusted", "aje", "rje", "tje", "tax_basis", "form_line_key"),
    ),
    "TXP-02 tallies": (wb.WorkbookTallyOut, ("state", "difference")),
    "TXP-05 K": (wb.WorkbookScheduleKLineOut, ("line", "total", "by_partner", "tie")),
    "TXP-06 structure": (
        wb.WorkbookAllocationStructureOut,
        ("kind", "status", "rungs", "seen_hash"),
    ),
    "TXP-07 capital": (
        wb.WorkbookCapitalRowOut,
        ("beginning", "contributions", "income", "distributions", "ending"),
    ),
    "TXP-10 issues": (wb.WorkbookReturnIssuesOut, ("items", "by_section", "by_step")),
    "TXP-11 cells": (
        wb.WorkbookCellOut,
        ("address", "value", "formula", "author", "state", "citation_ids"),
    ),
}


@pytest.mark.parametrize("need", sorted(NEEDS))
def test_every_screen_field_exists(need: str) -> None:
    model, fields = NEEDS[need]
    assert [f for f in fields if f not in model.model_fields] == [], need


def _paths() -> dict[str, dict[str, dict[str, object]]]:
    return cast(dict[str, dict[str, dict[str, object]]], json.loads(document())["paths"])


# Built in S40 (T-05-T31 run routes, T-05-T33 TB, T-05-T34 schedules, T-05-T35 cell edit): these
# publish no 501; every other route still does until its build row.
_R = "/v1/tax-returns/{return_id}"
BUILT = {
    ("PUT", f"{_R}/workbook/cells/{{address}}"),
    ("POST", f"{_R}/workbook-runs"),
    ("GET", f"{_R}/workbook-runs"),
    ("GET", f"{_R}/trial-balance"),
    ("GET", f"{_R}/trial-balance/tallies"),
    ("GET", f"{_R}/journal-entries"),
    ("GET", f"{_R}/schedules/k"),
    ("GET", f"{_R}/schedules/k/lines/{{line}}/breakdown"),
    ("GET", f"{_R}/capital-accounts"),
    ("GET", f"{_R}/schedules/m2"),
    # S41: T-05-T41 allocation structure, T-05-T40 imports, T-05-T42 sections.
    ("GET", f"{_R}/allocation-structure"),
    ("PUT", f"{_R}/allocation-structure/draft"),
    ("POST", f"{_R}/allocation-structure/preview"),
    ("POST", f"{_R}/allocation-structure/approve"),
    ("POST", f"{_R}/workbook/imports"),
    ("GET", f"{_R}/sections"),
    ("POST", f"{_R}/sections/{{key}}/sign-off"),
}


def test_every_route_is_published_with_a_501_until_built() -> None:
    paths = _paths()
    for route in wb.workbook_router.routes:
        for method in getattr(route, "methods", ()):
            op = paths[route.path][method.lower()]  # type: ignore[attr-defined] -- starlette route attributes
            responses = cast(dict[str, object], op["responses"])
            if (method, route.path) in BUILT:  # type: ignore[attr-defined] -- starlette route attributes
                assert "501" not in responses, route.path  # type: ignore[attr-defined] -- starlette route attributes
            else:
                assert "501" in responses, route.path  # type: ignore[attr-defined] -- starlette route attributes
    assert len(wb.workbook_router.routes) == 33  # S41: + allocation-structure/approve


HUMAN_VERBS = (
    "workbook.edit",
    "workbook.export",
    "workbook_import.create",
    "workbook_run.start",
    "tax_ownership.edit",
    "allocation_structure.edit",
    "tax_memo.draft",
    "tax_memo.edit",
)


def test_the_human_verbs_deny_the_agent_and_the_doc_names_each() -> None:
    actions = yaml.safe_load((ROOT / "docs/architecture/permission-matrix/tax.yaml").read_text())[
        "actions"
    ]
    doc = (ROOT / "docs/contracts/tax-workbook.md").read_text()
    human = doc.split("## 4. Human-only actions", 1)[1].split("## 5.", 1)[0]
    for action in HUMAN_VERBS:
        assert (actions[action]["agent"], actions[action]["system"]) == ("deny", "deny"), action
        assert f"`{action}`" in human, action


def test_values_and_memo_text_are_tax_return_information() -> None:
    for model, name in (
        (wb.WorkbookCellOut, "value"),
        (wb.WorkbookMemoSectionOut, "body"),
        (wb.WorkbookTbRowOut, "tax_basis"),
    ):
        schema = json.dumps(model.model_json_schema()["properties"][name])
        assert '"cls": "restricted"' in schema, (model, name)
    assert "tin" not in " ".join(wb.WorkbookPartnerOut.model_fields).replace("tin_last4", "")
