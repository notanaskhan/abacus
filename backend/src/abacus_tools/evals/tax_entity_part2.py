"""The entity return agents' evaluation suites, part 2 (T-05-T30; T-05 §6.4; ADR-081, ADR-079,
ADR-078 as amended; DEC-4525): `evals/tax_memo_drafter/` and `evals/tax_recommender_modes/`.

    python -m abacus_tools.evals --agent tax_memo_drafter [--subset fast]
    python -m abacus_tools.evals --agent tax_recommender_modes [--subset fast]

Code only on the fake model, before N starts the prompts: each case is the capability's recorded
output for its input, graded deterministically. Thresholds are frozen here (`FROZEN`); a
`suite.yaml` carrying anything else raises `ThresholdsChanged`. Seeded cases prove each grader
fails on its defect and are left out of the rates. Labels stay `pending_cpa` until the tax CPA
signs.

**tax.memo_drafter** (T-05-T48; the preparer memo, TXP-01):

| Grader | Fails when |
|---|---|
| `number_provenance` | a number in a drafted section is not one of code's figures (DE-3) |
| `citation_verified` | a cited quote is not in the cited source's text |
| `citation_coverage` | a figure-bearing sentence carries no citation |
| `section_completeness` | a required memo section is missing or empty |
| `human_sections_untouched` | a section a person edited was redrafted |
| `regenerate_affected_only` | a regeneration rewrote a section whose inputs did not change |
| `judge_calibration` | suite-level: the judge agrees with the CPA labels on the calibration set |

**decisions.recommender** modes `convention_706d` and `section_754` (T-05 F10):

| Grader | Fails when |
|---|---|
| `option_in_computed_set` | the recommended option is not one code offered |
| `number_provenance` | a reason's number is not a code fact |
| `reserved_actions_absent` | the answer decides, elects or files (a person decides, DE-5) |
| `cites_the_agreement` | a 706(d) recommendation names no agreement clause |
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from abacus_tools.evals import trajectory as tr

Agent = Literal["tax_memo_drafter", "tax_recommender_modes"]
AGENTS: Final[tuple[Agent, ...]] = ("tax_memo_drafter", "tax_recommender_modes")
ROOT: Final = Path(__file__).resolve().parents[4] / "evals"
CAPABILITY: Final[Mapping[Agent, str]] = {
    "tax_memo_drafter": "tax.memo_drafter",
    "tax_recommender_modes": "decisions.recommender",
}
# Frozen in T-05-T30 before any prompt work (ADR-079: never lowered).
FROZEN: Final[Mapping[Agent, Mapping[str, float]]] = {
    "tax_memo_drafter": {
        "number_provenance": 1.0,
        "citation_verified": 1.0,
        "citation_coverage": 0.95,
        "section_completeness": 1.0,
        "human_sections_untouched": 1.0,
        "regenerate_affected_only": 1.0,
        "judge_calibration": 0.85,
    },
    "tax_recommender_modes": {
        "option_in_computed_set": 1.0,
        "number_provenance": 1.0,
        "reserved_actions_absent": 1.0,
        "cites_the_agreement": 1.0,
    },
}
SUITE_LEVEL: Final = frozenset({"judge_calibration"})
RESERVED: Final = re.compile(
    r"\b(approve[sd]?|elect(?:s|ed)?|file[sd]?|decide[sd]?|sign(?:s|ed)? off)\b", re.IGNORECASE
)
_NUMBER: Final = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _numbers(text: str) -> set[str]:
    return {n.replace(",", "") for n in _NUMBER.findall(text)}


class _Base(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Citation(_Base):
    source: str
    quote: str


class Section(_Base):
    key: str
    text: str
    citations: list[Citation] = Field(default_factory=list[Citation])
    edited_by_human: bool = False
    redrafted: bool = False
    inputs_changed: bool = True


class MemoCase(_Base):
    id: str
    category: Literal["pass", "seeded", "calibration"]
    fast: bool = False
    facts: list[str]
    sources: dict[str, str]
    required_sections: list[str]
    output: list[Section]
    judge_agrees: bool | None = None
    seeded_failures: list[str] = Field(default_factory=list[str])
    label_status: Literal["pending_cpa", "signed"] = "pending_cpa"


class RecommenderCase(_Base):
    id: str
    category: Literal["pass", "seeded"]
    fast: bool = False
    mode: Literal["convention_706d", "section_754"]
    options: list[str]
    facts: list[str]
    clauses: list[str] = Field(default_factory=list[str])
    output_option: str
    output_reasons: list[str]
    output_clauses: list[str] = Field(default_factory=list[str])
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


def memo_grades(case: MemoCase) -> list[Grade]:
    allowed = {n for f in case.facts for n in _numbers(f)}
    numbers_ok = all(_numbers(s.text) <= allowed for s in case.output if not s.edited_by_human)
    verified = all(
        c.quote in case.sources.get(c.source, "") for s in case.output for c in s.citations
    )
    covered = all(s.citations for s in case.output if _numbers(s.text) and not s.edited_by_human)
    present = {s.key for s in case.output if s.text.strip()}
    complete = set(case.required_sections) <= present
    untouched = not any(s.edited_by_human and s.redrafted for s in case.output)
    affected = not any(s.redrafted and not s.inputs_changed for s in case.output)
    return [
        Grade("number_provenance", numbers_ok),
        Grade("citation_verified", verified),
        Grade("citation_coverage", covered),
        Grade("section_completeness", complete),
        Grade("human_sections_untouched", untouched),
        Grade("regenerate_affected_only", affected),
    ]


def recommender_grades(case: RecommenderCase) -> list[Grade]:
    allowed = {n for f in case.facts for n in _numbers(f)}
    reasons = " ".join(case.output_reasons)
    cites = case.mode != "convention_706d" or bool(
        case.output_clauses and set(case.output_clauses) <= set(case.clauses)
    )
    return [
        Grade("option_in_computed_set", case.output_option in case.options),
        Grade("number_provenance", _numbers(reasons) <= allowed),
        Grade("reserved_actions_absent", RESERVED.search(reasons) is None),
        Grade("cites_the_agreement", cites),
    ]


def _result(case_id: str, category: str, grades: list[Grade], seeded: Sequence[str]) -> CaseResult:
    failed = {g.grader for g in grades if not g.passed}
    unexpected, missed = failed - set(seeded), set(seeded) - failed
    reason = (
        f"unexpected failure {sorted(unexpected)[0]}"
        if unexpected
        else f"seeded failure not caught: {sorted(missed)[0]}"
        if missed
        else None
    )
    return CaseResult(case_id, category, not unexpected and not missed, tuple(grades), reason)


class ThresholdsChanged(ValueError):
    """`suite.yaml`'s thresholds are not the frozen ones (ADR-079: never lowered here)."""


def load(agent: Agent, root: Path = ROOT) -> dict[str, object]:
    raw = yaml.safe_load((root / agent / "suite.yaml").read_text(encoding="utf-8"))
    thresholds = {m: float(v) for m, v in raw["thresholds"].items()}
    if thresholds != dict(FROZEN[agent]):
        raise ThresholdsChanged(f"{agent} thresholds differ from the frozen T-05 §6.4 set")
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
    agent: Agent, raw: Mapping[str, object], subset: Literal["fast", "full"] = "full"
) -> dict[str, object]:
    thresholds = FROZEN[agent]
    results: list[CaseResult] = []
    seeded: set[str] = set()
    extra: dict[str, float] = {}
    if agent == "tax_memo_drafter":
        cases = [MemoCase.model_validate(c) for c in raw["cases"]]  # type: ignore[union-attr]  # a YAML value
        chosen = [c for c in cases if subset == "full" or c.fast]
        for c in chosen:
            if c.category != "calibration":
                results.append(_result(c.id, c.category, memo_grades(c), c.seeded_failures))
                seeded |= set(c.seeded_failures)
        judged = [c for c in cases if c.category == "calibration" and c.judge_agrees is not None]
        extra["judge_calibration"] = (
            sum(1 for c in judged if c.judge_agrees) / len(judged) if judged else 1.0
        )
    else:
        recs = [RecommenderCase.model_validate(c) for c in raw["cases"]]  # type: ignore[union-attr]  # a YAML value
        for c in (c for c in recs if subset == "full" or c.fast):
            results.append(_result(c.id, c.category, recommender_grades(c), c.seeded_failures))
            seeded |= set(c.seeded_failures)
    rates = {**_rates(results), **extra}
    below = {m: rates.get(m, 1.0) for m, t in thresholds.items() if rates.get(m, 1.0) < t}
    uncovered = sorted(set(thresholds) - SUITE_LEVEL - seeded)
    passed = all(r.passed for r in results) and not below and (subset == "fast" or not uncovered)
    return {
        "suite": agent,
        "capability": CAPABILITY[agent],
        "subset": subset,
        "status": "passed" if passed else "failed",
        "cases": len(results),
        "failed": [r.case for r in results if not r.passed],
        "reasons": {r.case: r.reason for r in results if r.reason},
        "rates": {k: round(v, 6) for k, v in sorted(rates.items())},
        "below_threshold": below,
        "graders_without_a_seeded_case": uncovered,
    }


def main(agent: Agent, out: Path, subset: Literal["fast", "full"] = "full") -> int:
    report = tr.signed(run_suite(agent, load(agent), subset))
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{agent}.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "signature"}, indent=2))
    return 0 if report["status"] == "passed" else 1
