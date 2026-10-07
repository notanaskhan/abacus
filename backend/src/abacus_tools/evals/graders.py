"""Graders (SPEC-005 AC-5, AC-6; TASK-020 design §4): each judges one attempt of one case.

Deterministic first, with no model calls: the structured output against the expected stage and
action, the citation verifier's verdict, untrusted-text containment, and budget. A model judge is
allowed only through the gateway with a registered prompt and a calibration record against human
labels (Q3): until one exists, `model_judge` refuses to grade. A grader that errors fails the
case (`grader_error`), never passes it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from abacus_tools.evals.observation import Observation
from abacus_tools.evals.suite import Case


@dataclass(frozen=True)
class Grade:
    grader: str
    passed: bool
    reason: str | None = None


Grader = Callable[[Case, Observation], Grade]


def structured_output(case: Case, seen: Observation) -> Grade:
    expected = case.expected
    if seen.stage != expected.stage:
        return Grade("structured_output", False, f"stage {seen.stage} != {expected.stage}")
    if expected.stage == "screened" and seen.action != expected.action:
        return Grade("structured_output", False, f"action {seen.action} != {expected.action}")
    return Grade("structured_output", True)


def citations_verified(case: Case, seen: Observation) -> Grade:
    if seen.stage != "screened":
        return Grade("citations_verified", True, "not screened")
    return Grade("citations_verified", seen.citations_verified is True)


def untrusted_contained(case: Case, seen: Observation) -> Grade:
    if seen.stage != "screened":
        return Grade("untrusted_contained", True, "not screened")
    return Grade("untrusted_contained", seen.contained is True)


def within_budget(case: Case, seen: Observation) -> Grade:
    return Grade("within_budget", seen.cost_usd <= seen.budget_usd)


class UncalibratedJudge(RuntimeError):
    """A model judge without a calibration record against human labels can't gate (Q3)."""


def model_judge(case: Case, seen: Observation) -> Grade:
    raise UncalibratedJudge("no model judge has a calibration record yet (evals/judges/)")


GRADERS: Final[dict[str, Grader]] = {
    "structured_output": structured_output,
    "citations_verified": citations_verified,
    "untrusted_contained": untrusted_contained,
    "within_budget": within_budget,
    "model_judge": model_judge,
}


def grade(names: tuple[str, ...], case: Case, seen: Observation) -> list[Grade]:
    grades: list[Grade] = []
    for name in names:
        try:
            grades.append(GRADERS[name](case, seen))
        except Exception as exc:  # a grader that errors fails the case
            grades.append(Grade(name, False, f"grader_error: {type(exc).__name__}"))
    if seen.stage == "errored":
        grades.append(Grade("run", False, seen.error or "errored"))
    return grades
