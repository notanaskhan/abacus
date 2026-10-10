"""SPEC-026 AC-6 (TASK-049): the milestone report for a run. Recall on "needs revision" (the
dangerous error) with every miss, results per failure-taxonomy and adversarial category, and the
cost of a screening against the agent spec's budget."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from statistics import mean

from pydantic import BaseModel, ConfigDict

from abacus_tools.evals.metrics import (
    Attempt,
    caught,
    needs_revision,
    needs_revision_recall,
    ready_precision,
)
from abacus_tools.evals.taxonomy import ADVERSARIAL_CATEGORIES, FAILURE_CATEGORIES

ESCALATED = "Escalated"  # an attempt's error when the screener escalated instead of answering


class Miss(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str
    attempt: int
    categories: tuple[str, ...]
    proposed: str | None


class Report(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    needs_revision_recall: float
    misses: tuple[Miss, ...]
    recall_by_category: dict[str, float]
    containment_by_category: dict[str, float]
    ready_precision: float
    screenings: int
    cost_mean_usd: Decimal
    cost_p95_usd: Decimal
    cost_max_usd: Decimal
    budget_per_screening_usd: Decimal
    over_budget: int
    total_cost_usd: Decimal
    cost_limit_usd: Decimal
    escalations: int
    ece: float | None
    latency_p50_ms: int | None
    latency_p95_ms: int | None


def _p(values: Sequence[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(q * (len(ordered) - 1)))]


def milestone(
    attempts: Sequence[Attempt],
    *,
    budget_per_screening: Decimal,
    cost_limit: Decimal,
    ece: float | None,
) -> Report:
    relevant = [(c, s) for c, s in attempts if needs_revision(c)]
    misses = tuple(
        Miss(
            case_id=c.id,
            attempt=s.attempt,
            categories=tuple(sorted(c.categories)),
            proposed=s.action,
        )
        for c, s in relevant
        if not caught(s)
    )
    recall: dict[str, float] = {}
    for category in sorted(FAILURE_CATEGORIES):
        found = [s for c, s in relevant if category in c.categories]
        if found:
            recall[category] = sum(caught(s) for s in found) / len(found)
    containment: dict[str, float] = {}
    for category in sorted(ADVERSARIAL_CATEGORIES):
        found = [s for c, s in attempts if category in c.categories and s.stage == "screened"]
        if found:
            containment[category] = sum(s.contained is True for s in found) / len(found)
    screened = [s for _, s in attempts if s.stage == "screened"]
    costs = [float(s.cost_usd) for s in screened]
    latencies = [float(s.latency_ms) for s in screened if s.latency_ms is not None]
    return Report(
        needs_revision_recall=needs_revision_recall(attempts),
        misses=misses,
        recall_by_category=recall,
        containment_by_category=containment,
        ready_precision=ready_precision(attempts),
        screenings=len(screened),
        cost_mean_usd=Decimal(str(round(mean(costs), 6))) if costs else Decimal(0),
        cost_p95_usd=Decimal(str(round(_p(costs, 0.95), 6))) if costs else Decimal(0),
        cost_max_usd=Decimal(str(round(max(costs), 6))) if costs else Decimal(0),
        budget_per_screening_usd=budget_per_screening,
        over_budget=sum(s.cost_usd > budget_per_screening for s in screened),
        total_cost_usd=sum((s.cost_usd for _, s in attempts), Decimal(0)),
        cost_limit_usd=cost_limit,
        escalations=sum(s.error == ESCALATED for _, s in attempts),
        ece=ece,
        latency_p50_ms=round(_p(latencies, 0.5)) if latencies else None,
        latency_p95_ms=round(_p(latencies, 0.95)) if latencies else None,
    )


def render(report: Report) -> str:
    """A plain table for the end of a run."""
    lines = [
        f"needs-revision recall  {report.needs_revision_recall:.3f}  "
        f"({len(report.misses)} missed)",
        *(
            f"  missed {m.case_id} #{m.attempt} [{', '.join(m.categories)}] -> {m.proposed}"
            for m in report.misses
        ),
        f"ready precision        {report.ready_precision:.3f}",
        "recall by category     "
        + ", ".join(f"{k} {v:.2f}" for k, v in report.recall_by_category.items()),
        "containment            "
        + ", ".join(f"{k} {v:.2f}" for k, v in report.containment_by_category.items()),
        f"cost per screening     mean ${report.cost_mean_usd} p95 ${report.cost_p95_usd} "
        f"max ${report.cost_max_usd} (budget ${report.budget_per_screening_usd}; "
        f"{report.over_budget} over)",
        f"run cost               ${report.total_cost_usd} of ${report.cost_limit_usd}",
        f"escalations {report.escalations}  ECE {report.ece}  "
        f"latency p50 {report.latency_p50_ms} ms p95 {report.latency_p95_ms} ms",
    ]
    return "\n".join(lines)
