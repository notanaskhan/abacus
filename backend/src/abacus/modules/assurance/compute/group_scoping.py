"""Group scoping by code (A-09-T23; A-09 §3 F5; SPEC-658; AUD-34; AU-C 600; ADR-050). Pure.

- **Group materiality** is the EP's choice among A-04's options; performance materiality is 75%
  of it and clearly trivial 5% (the firm standard's defaults): 240,000 gives 180,000 and 12,000.
- **Component PM** defaults from the firm-standard table (a fraction of group PM by the
  component's share) and must stay below group PM: at or above it answers 422.
- **Coverage** is each component's contribution to the consolidated figure after eliminations,
  split into the components scoped in (full scope or specific procedures) and the rest, as whole
  percents half up (Harlow & Pike: 78% and 22% of 50,760,000).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Final, Literal

PM_PCT: Final = Decimal("75")
CT_PCT: Final = Decimal("5")
HUNDRED: Final = Decimal(100)
CENT: Final = Decimal("0.01")
# The firm-standard table: a component's share of the group figure → its PM as a % of group PM.
DEFAULT_TABLE: Final[tuple[tuple[Decimal, Decimal], ...]] = (
    (Decimal("50"), Decimal("75")),
    (Decimal("25"), Decimal("60")),
    (Decimal("10"), Decimal("50")),
    (Decimal("0"), Decimal("40")),
)
Planned = Literal["full_scope", "specific_procedures", "analytical_only"]


class ComponentPmTooHigh(ValueError):
    code = "component_pm_not_below_group_pm"


@dataclass(frozen=True)
class GroupThresholds:
    materiality: Decimal
    pm: Decimal
    ct: Decimal


@dataclass(frozen=True)
class Coverage:
    total: Decimal
    covered: Decimal
    covered_pct: Decimal
    not_covered: Decimal
    not_covered_pct: Decimal


def _q(value: Decimal) -> Decimal:
    return Decimal(value).quantize(CENT)


def thresholds(materiality: Decimal) -> GroupThresholds:
    m = _q(materiality)
    return GroupThresholds(m, _q(m * PM_PCT / HUNDRED), _q(m * CT_PCT / HUNDRED))


def default_component_pm(group_pm: Decimal, share_pct: Decimal) -> Decimal:
    for floor, pct in DEFAULT_TABLE:
        if share_pct >= floor:
            return _q(group_pm * pct / HUNDRED)
    return _q(group_pm * DEFAULT_TABLE[-1][1] / HUNDRED)


def validate_component_pm(component_pm: Decimal, group_pm: Decimal) -> Decimal:
    if component_pm <= 0 or component_pm >= group_pm:
        raise ComponentPmTooHigh(f"{component_pm} >= {group_pm}")
    return _q(component_pm)


def _pct(part: Decimal, whole: Decimal) -> Decimal:
    if whole == 0:
        return Decimal(0)
    return (part * HUNDRED / whole).quantize(Decimal(1), rounding=ROUND_HALF_UP)


def coverage(
    contributions: Mapping[str, Decimal], planned: Mapping[str, Planned], total: Decimal
) -> Coverage:
    """Contributions after eliminations; a component is covered unless only analytics."""
    covered = sum(
        (
            v
            for k, v in contributions.items()
            if planned.get(k, "analytical_only") != "analytical_only"
        ),
        Decimal(0),
    )
    rest = _q(Decimal(total) - covered)
    return Coverage(_q(total), _q(covered), _pct(covered, total), rest, _pct(rest, total))


def aggregation_facts(uncorrected: Sequence[Decimal], group_pm: Decimal) -> Mapping[str, Decimal]:
    """The aggregation risk facts: the components' uncorrected total and its share of group PM."""
    total = _q(sum((abs(Decimal(x)) for x in uncorrected), Decimal(0)))
    return {"uncorrected_total": total, "pct_of_group_pm": _pct(total, group_pm)}
