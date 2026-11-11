"""Q-04-T136 (TASK-6739; DEC-3305): the A-07 shadow comparison. "Each audit firm has one shadowed
engagement with a recorded comparison against its own tool." The compare is code; a difference
is read by a person."""

from __future__ import annotations

import uuid
from datetime import date
from pathlib import Path

import yaml

from abacus_tools.a07_shadow import compare, render

REPO = Path(__file__).resolve().parents[3]
TOOL = REPO / "docs" / "ops" / "pilot" / "pf-x1" / "a07-shadow-firm-tool.yaml"
ACCRUED = {
    "report_released_on": date(2026, 10, 9),
    "documentation_completion_date": date(2026, 12, 8),
    "archived_on": date(2026, 12, 3),
}
MET = {"G5": True, "G6": True, "G7": True}


def _tool() -> dict[str, object]:
    return yaml.safe_load(TOOL.read_text(encoding="utf-8"))


def test_ac_pf_x1s_northwind_matches_its_own_tool_on_every_check() -> None:
    checks = compare(ACCRUED, MET, _tool())
    assert [c.outcome for c in checks] == ["match"] * 4
    report = render(
        "Northwind Robotics 401(k) Plan PY2025", "the tool", uuid.uuid4(), checks, True
    )
    assert "synthetic, PF-X1" in report
    assert "No differences" in report


def test_a_one_day_drift_differs_and_says_so() -> None:
    drift = {**ACCRUED, "archived_on": date(2026, 12, 4)}
    checks = compare(drift, MET, _tool())
    by = {c.key: c.outcome for c in checks}
    assert by["archived_on"] == "differs"
    assert "1 difference(s) to read." in render("E", "T", uuid.uuid4(), checks, False)


def test_an_open_gate_on_the_firms_release_date_differs() -> None:
    checks = compare(ACCRUED, {**MET, "G7": False}, _tool())
    gate = next(c for c in checks if c.key == "gates_at_release")
    assert gate.outcome == "differs" and gate.accrued == "open: G7"


def test_a_missing_date_is_not_yet_comparable() -> None:
    checks = compare({**ACCRUED, "archived_on": None}, MET, {**_tool(), "report_released_on": ""})
    by = {c.key: c.outcome for c in checks}
    assert by["archived_on"] == "not_yet"
    assert by["report_released_on"] == "not_yet"
    assert by["gates_at_release"] == "not_yet"
