"""The workbook fix mode's evaluation suite (T-05-T50 rest; TASK-7932; ADR-079, ADR-078 as
amended; DEC-4927): `evals/workbook_fix/`, `issues.fix_runner.workbook@v1`.

    python -m abacus_tools.evals --agent workbook_fix [--subset fast]

Code only on the fake model: each case is the mode's recorded answer for a person's free-text
fix instructions, run through the product's own check (`tax.workbook_fix.kept`) and graded
deterministically. Thresholds are frozen here (`FROZEN`) before the prompt; a `suite.yaml`
carrying anything else raises `ThresholdsChanged`. Seeded cases prove each grader fails on its
defect and are left out of the rates.

| Grader | Fails when |
|---|---|
| `cells_named_only` | the kept cells are not exactly the ones the person named |
| `amount_provenance` | an answer's amount is not one the person wrote (DE-3, ADR-050) |
| `sheets_on_the_form` | an answer names a sheet the form does not have |
| `no_cell_when_unnamed` | instructions naming no cell keep a cell |
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from abacus_tools.evals import trajectory as tr

ROOT: Final = Path(__file__).resolve().parents[4] / "evals"
SUITE: Final = "workbook_fix"
CAPABILITY: Final = "issues.fix_runner"
PROMPT: Final = "issues.fix_runner.workbook@v1"
# Frozen in T-05-T50 rest before any prompt work (ADR-079: never lowered).
FROZEN: Final[Mapping[str, float]] = {
    "cells_named_only": 1.0,
    "amount_provenance": 1.0,
    "sheets_on_the_form": 1.0,
    "no_cell_when_unnamed": 1.0,
}


class _Change(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    sheet: str
    cell: str
    op: Literal["add", "subtract", "set"]
    amount: str


class Case(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    category: Literal["pass", "seeded"]
    fast: bool = False
    form: str = "1065"
    instructions: str
    # The cells the person named (`07!B6`), as the case's author reads them.
    expected: list[str] = Field(default_factory=list[str])
    output: list[_Change] = Field(default_factory=list[_Change])
    seeded_failures: list[str] = Field(default_factory=list[str])


@dataclass(frozen=True)
class Grade:
    grader: str
    passed: bool


@dataclass(frozen=True)
class CaseResult:
    case: str
    category: str
    passed: bool
    grades: tuple[Grade, ...]
    reason: str | None


def grades(case: Case) -> list[Grade]:
    from abacus.modules.tax.api import (
        WorkbookFixChange,
        WorkbookFixJudgment,
        workbook_fix_amounts,
        workbook_fix_kept,
        workbook_sheets,
    )

    answer = WorkbookFixJudgment(
        changes=[WorkbookFixChange(**c.model_dump()) for c in case.output]
    )
    planned = {p.at.key for p in workbook_fix_kept(answer, case.instructions, case.form)}
    written = workbook_fix_amounts(case.instructions)
    sheets = {k for k, _ in workbook_sheets(case.form)}
    raw = {f"{c.sheet}!{c.cell.upper()}" for c in case.output}
    return [
        Grade("cells_named_only", planned == set(case.expected)),
        Grade("amount_provenance", all(c.amount.strip() in written for c in case.output)),
        Grade("sheets_on_the_form", all(c.sheet in sheets for c in case.output)),
        Grade("no_cell_when_unnamed", bool(case.expected) or not raw),
    ]


def _result(case: Case) -> CaseResult:
    gs = grades(case)
    failed = {g.grader for g in gs if not g.passed}
    unexpected, missed = failed - set(case.seeded_failures), set(case.seeded_failures) - failed
    reason = (
        f"unexpected failure {sorted(unexpected)[0]}"
        if unexpected
        else f"seeded failure not caught: {sorted(missed)[0]}"
        if missed
        else None
    )
    return CaseResult(case.id, case.category, not unexpected and not missed, tuple(gs), reason)


class ThresholdsChanged(ValueError):
    """`suite.yaml`'s thresholds are not the frozen ones (ADR-079: never lowered here)."""


def load(root: Path = ROOT) -> dict[str, object]:
    raw = yaml.safe_load((root / SUITE / "suite.yaml").read_text(encoding="utf-8"))
    thresholds = {m: float(v) for m, v in raw["thresholds"].items()}
    if thresholds != dict(FROZEN):
        raise ThresholdsChanged("workbook_fix thresholds differ from the frozen set")
    if raw.get("prompt") != PROMPT:
        raise ThresholdsChanged("workbook_fix names another prompt")
    return raw


def _rates(results: Sequence[CaseResult]) -> dict[str, float]:
    totals: dict[str, list[int]] = {}
    for r in results:
        if r.category != "pass":
            continue
        for g in r.grades:
            seen = totals.setdefault(g.grader, [0, 0])
            seen[0] += int(g.passed)
            seen[1] += 1
    return {k: (v[0] / v[1] if v[1] else 1.0) for k, v in totals.items()}


def run_suite(
    raw: Mapping[str, object], subset: Literal["fast", "full"] = "full"
) -> dict[str, object]:
    cases = [Case.model_validate(c) for c in raw["cases"]]  # type: ignore[union-attr]  # a YAML value
    results = [_result(c) for c in cases if subset == "full" or c.fast]
    seeded = {g for c in cases if subset == "full" or c.fast for g in c.seeded_failures}
    rates = _rates(results)
    below = {m: rates.get(m, 1.0) for m, t in FROZEN.items() if rates.get(m, 1.0) < t}
    uncovered = sorted(set(FROZEN) - seeded)
    passed = all(r.passed for r in results) and not below and (subset == "fast" or not uncovered)
    return {
        "suite": SUITE,
        "capability": CAPABILITY,
        "prompt": PROMPT,
        "subset": subset,
        "status": "passed" if passed else "failed",
        "cases": len(results),
        "failed": [r.case for r in results if not r.passed],
        "reasons": {r.case: r.reason for r in results if r.reason},
        "rates": {k: round(v, 6) for k, v in sorted(rates.items())},
        "below_threshold": below,
        "graders_without_a_seeded_case": uncovered,
    }


def main(out: Path, subset: Literal["fast", "full"] = "full") -> int:
    report = tr.signed(run_suite(load(), subset))
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{SUITE}.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "signature"}, indent=2))
    return 0 if report["status"] == "passed" else 1
