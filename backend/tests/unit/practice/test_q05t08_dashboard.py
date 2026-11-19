"""Q-05-T08 (TASK-8715; SPEC-711 AC-1, AC-2; DEC-5711): component health from registered signals
or an owner flag. Ana Cruz's missing confirmation (an independence gap) puts Relevant ethical
requirements At risk; an agent above tolerance puts engagement performance At risk; an open
finding past due is overdue remediation; days to the evaluation count from today."""

from __future__ import annotations

from datetime import date

from abacus.modules.practice.compute.quality_dashboard import (
    FindingFacts,
    ObjectiveFacts,
    at_risk_objectives,
    components,
    days_to,
)

TODAY = date(2026, 9, 14)
OBJECTIVES = [ObjectiveFacts("ethical_requirements", False)] + [
    ObjectiveFacts("resources", False)
] * 23


def _health(signals: dict[str, int], findings: list[FindingFacts] | None = None) -> dict[str, str]:
    return {h.component: h.health for h in components(OBJECTIVES, findings or [], signals, TODAY)}


def test_ac_an_independence_gap_puts_ethical_requirements_at_risk() -> None:
    health = _health({"independence_gap": 1})
    assert health["ethical_requirements"] == "at_risk"
    assert health["resources"] == "ok"
    out = components(OBJECTIVES, [], {"independence_gap": 1}, TODAY)
    assert at_risk_objectives(OBJECTIVES, out) == 1


def test_ac_an_agent_over_tolerance_and_an_owner_flag() -> None:
    health = _health({"agent_over_tolerance": 2})
    assert health["engagement_performance"] == "at_risk"
    flagged = [ObjectiveFacts("governance_leadership", True), *OBJECTIVES]
    out = {h.component: h.signals for h in components(flagged, [], {}, TODAY)}
    assert out["governance_leadership"] == ("owner_flag",)


def test_ac_overdue_remediation_and_days_to_the_evaluation() -> None:
    late = [FindingFacts("resources", "open", date(2026, 9, 1))]
    assert _health({}, late)["resources"] == "at_risk"
    assert (
        _health({}, [FindingFacts("resources", "remediated", date(2026, 9, 1))])["resources"]
        == "ok"
    )
    assert days_to(date(2026, 12, 15), TODAY) == 92
