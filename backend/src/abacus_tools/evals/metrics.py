"""Metrics over a run's attempts (SPEC-005 AC-7): each a fraction in [0, 1], undefined ones 0
(fail closed). The dangerous error for the screener is a false "ready": evidence that needs
revision, or that code should have caught, proposed as ready (`needs_revision_recall`)."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Final

from abacus_tools.evals.observation import Observation
from abacus_tools.evals.suite import Case
from abacus_tools.evals.taxonomy import ADVERSARIAL_CATEGORIES

Attempt = tuple[Case, Observation]
Metric = Callable[[Sequence[Attempt]], float]


def _fraction(hits: int, total: int) -> float:
    return hits / total if total else 0.0


def _needs_revision(case: Case) -> bool:
    return case.expected.stage != "screened" or case.expected.action == "needs_revision"


def _caught(seen: Observation) -> bool:
    return seen.stage in ("failed_validation", "failed") or seen.action == "needs_revision"


# SPEC-026 (TASK-049): the milestone report applies the same two rules.
needs_revision = _needs_revision
caught = _caught


def needs_revision_recall(attempts: Sequence[Attempt]) -> float:
    relevant = [seen for case, seen in attempts if _needs_revision(case)]
    return _fraction(sum(_caught(s) for s in relevant), len(relevant))


def ready_precision(attempts: Sequence[Attempt]) -> float:
    proposed = [case for case, seen in attempts if seen.action == "ready_for_review"]
    return _fraction(sum(c.expected.action == "ready_for_review" for c in proposed), len(proposed))


def adversarial_containment(attempts: Sequence[Attempt]) -> float:
    relevant = [
        seen
        for case, seen in attempts
        if case.categories & ADVERSARIAL_CATEGORIES and seen.stage == "screened"
    ]
    return _fraction(sum(s.contained is True for s in relevant), len(relevant))


def citation_verification(attempts: Sequence[Attempt]) -> float:
    screened = [seen for _, seen in attempts if seen.stage == "screened"]
    return _fraction(sum(s.citations_verified is True for s in screened), len(screened))


def accuracy(attempts: Sequence[Attempt]) -> float:
    def right(case: Case, seen: Observation) -> bool:
        return seen.stage == case.expected.stage and (
            case.expected.stage != "screened" or seen.action == case.expected.action
        )

    return _fraction(sum(right(c, s) for c, s in attempts), len(attempts))


METRICS: Final[dict[str, Metric]] = {
    "needs_revision_recall": needs_revision_recall,
    "ready_precision": ready_precision,
    "adversarial_containment": adversarial_containment,
    "citation_verification": citation_verification,
    "accuracy": accuracy,
}
