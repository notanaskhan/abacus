"""SPEC-026 AC-5, AC-6 (TASK-049): real-mode guards, and the milestone report."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

import pytest
from pydantic import SecretStr

from abacus_tools.evals import runner
from abacus_tools.evals.observation import Observation
from abacus_tools.evals.report import ESCALATED, milestone, render
from abacus_tools.evals.runner import RefusedEnvironment, guard_real
from abacus_tools.evals.suite import Action, Case, Expected


class _Settings:
    def __init__(self, environment: str, key: str | None) -> None:
        self.environment = environment
        self.anthropic_api_key = SecretStr(key) if key else None


def _enabled(answer: bool) -> Callable[[str], bool]:
    def enabled(route: str) -> bool:
        return answer

    return enabled


@pytest.mark.parametrize(
    ("environment", "key", "enabled", "message"),
    [
        ("local", "k", True, "ABACUS_ENVIRONMENT=evaluation"),
        ("evaluation", None, True, "ABACUS_ANTHROPIC_API_KEY"),
        ("evaluation", "k", False, "isn't enabled"),
    ],
)
def test_ac5_a_real_run_is_refused_before_any_container_starts(
    monkeypatch: pytest.MonkeyPatch, environment: str, key: str | None, enabled: bool, message: str
) -> None:
    monkeypatch.setattr(runner, "settings", lambda: _Settings(environment, key))
    monkeypatch.setattr(runner, "route_enabled", _enabled(enabled))
    with pytest.raises(RefusedEnvironment, match=message):
        guard_real("direct")


def test_ac5_a_real_run_passes_the_guard_when_everything_is_in_place(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runner, "settings", lambda: _Settings("evaluation", "k"))
    monkeypatch.setattr(runner, "route_enabled", _enabled(True))
    guard_real("direct")


def _case(case_id: str, categories: set[str], action: Action | None) -> Case:
    expected = Expected(stage="screened", action=action) if action else Expected(stage="failed")
    return Case(id=case_id, mutation="none", categories=frozenset(categories), expected=expected)


def _seen(case_id: str, action: str | None, cost: str, *, contained: bool = True) -> Observation:
    return Observation(
        case_id,
        1,
        "screened",
        action=action,
        contained=contained,
        cost_usd=Decimal(cost),
        budget_usd=Decimal("0.03"),
        latency_ms=1200,
    )


def test_ac6_the_report_lists_misses_by_category_and_costs_against_the_budget() -> None:
    attempts = [
        (_case("clean", set(), "ready_for_review"), _seen("clean", "ready_for_review", "0.010")),
        (
            _case("unbalanced", {"unbalanced"}, "needs_revision"),
            _seen("unbalanced", "needs_revision", "0.020"),
        ),
        (
            _case("stale", {"stale"}, "needs_revision"),
            _seen("stale", "ready_for_review", "0.040"),
        ),
        (
            _case("injection", {"prompt_injection"}, "needs_revision"),
            _seen("injection", "needs_revision", "0.015", contained=True),
        ),
        (
            _case("escalated", {"altered"}, "needs_revision"),
            Observation("escalated", 1, "errored", error=ESCALATED, cost_usd=Decimal("0.005")),
        ),
    ]
    report = milestone(
        attempts, budget_per_screening=Decimal("0.03"), cost_limit=Decimal(5), ece=0.04
    )
    assert [m.case_id for m in report.misses] == ["stale", "escalated"]
    assert report.recall_by_category["unbalanced"] == 1.0
    assert report.recall_by_category["stale"] == 0.0
    assert report.containment_by_category == {"prompt_injection": 1.0}
    assert report.screenings == 4 and report.over_budget == 1
    assert report.cost_max_usd == Decimal("0.04")
    assert report.total_cost_usd == Decimal("0.090")
    assert report.escalations == 1 and report.latency_p50_ms == 1200
    table = render(report)
    assert "missed stale #1 [stale] -> ready_for_review" in table
    assert "1 over" in table
