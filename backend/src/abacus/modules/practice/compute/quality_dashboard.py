"""ADM-11's dashboard figures (Q-05-T08; TASK-8715; SPEC-711 AC-1, AC-2; DEC-5711), pure.

A component is At risk when an owner flagged one of its objectives, or when a registered signal
says so: an ethical-requirements objective while any independence confirmation is missing, an
engagement-performance objective while any agent is above tolerance, any component with an open
finding past due or open deficiencies linked to it. Objectives stay firm-wide when an office is
chosen (only the override rate and accuracy recompute by office).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Final, Literal

Health = Literal["ok", "at_risk"]
COMPONENTS: Final = (
    "governance_leadership",
    "ethical_requirements",
    "acceptance_continuance",
    "engagement_performance",
    "resources",
    "information_communication",
)
SIGNAL_COMPONENT: Final = {
    "independence_gap": "ethical_requirements",
    "agent_over_tolerance": "engagement_performance",
}


@dataclass(frozen=True, slots=True)
class ObjectiveFacts:
    component: str
    flagged: bool


@dataclass(frozen=True, slots=True)
class FindingFacts:
    component: str | None
    status: str
    due_on: date | None


@dataclass(frozen=True, slots=True)
class ComponentHealth:
    component: str
    health: Health
    signals: tuple[str, ...] = field(default_factory=tuple)


def components(
    objectives: Sequence[ObjectiveFacts],
    findings: Iterable[FindingFacts],
    signals: Mapping[str, int],
    today: date,
) -> list[ComponentHealth]:
    """Each component's health and the signals that made it At risk, in the register's order."""
    reasons: dict[str, list[str]] = {c: [] for c in COMPONENTS}
    for o in objectives:
        if o.flagged and "owner_flag" not in reasons.get(o.component, []):
            reasons.setdefault(o.component, []).append("owner_flag")
    for name, count in signals.items():
        target = SIGNAL_COMPONENT.get(name)
        if target is not None and count > 0:
            reasons[target].append(name)
    for f in findings:
        overdue = f.status != "remediated" and f.due_on is not None and f.due_on < today
        if (
            overdue
            and f.component is not None
            and "overdue_remediation" not in reasons[f.component]
        ):
            reasons[f.component].append("overdue_remediation")
    return [
        ComponentHealth(c, "at_risk" if reasons[c] else "ok", tuple(reasons[c]))
        for c in COMPONENTS
    ]


def at_risk_objectives(
    objectives: Sequence[ObjectiveFacts], health: Sequence[ComponentHealth]
) -> int:
    """Objectives counted At risk: flagged ones, plus every objective of a component a signal put
    At risk (2 of 24 on Sep 14, 2026)."""
    signalled = {h.component for h in health if any(s != "owner_flag" for s in h.signals)}
    return sum(1 for o in objectives if o.flagged or o.component in signalled)


def days_to(evaluation: date, today: date) -> int:
    return (evaluation - today).days


__all__ = [
    "COMPONENTS",
    "ComponentHealth",
    "FindingFacts",
    "ObjectiveFacts",
    "at_risk_objectives",
    "components",
    "days_to",
]
