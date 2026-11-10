"""Accounting estimates (A-05-T53; A-05 §4.4 `estimates`; AUD-27; AU-C 540): pure functions.

Granite Peak's inventory reserve: components 214,000 + 199,000 + 73,000 = 486,000 foot to TB 1450;
the rollforward 412,000 - 398,000 + 472,000 = 486,000; the retrospective compares a prior
estimate with how it resolved (|412,000 - 398,000| = 14,000 = 3.4% of 412,000; 4,500 = 5.4% of
84,000); the point estimate sits inside the auditor's range 451,000 to 512,000; bias indicators are
the retrospective differences' directions. Decimal only; percentages to one decimal place, half up.
The text that cites these numbers is drafted elsewhere and never computes (ADR-050).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Final, Literal

ENGINE_NAME: Final = "estimates"
ENGINE_VERSION: Final = "1"
_ZERO: Final = Decimal(0)
_TENTH: Final = Decimal("0.1")
Direction = Literal["over", "under", "exact"]


@dataclass(frozen=True)
class Footing:
    components_total: Decimal
    balance: Decimal
    difference: Decimal

    @property
    def foots(self) -> bool:
        return self.difference == _ZERO


@dataclass(frozen=True)
class Rollforward:
    opening: Decimal
    usage: Decimal
    additions: Decimal
    computed_closing: Decimal
    balance: Decimal

    @property
    def rolls(self) -> bool:
        return self.computed_closing == self.balance


@dataclass(frozen=True)
class Retrospective:
    """A prior estimate against its outcome: the difference and its share of the estimate."""

    label: str
    prior_estimate: Decimal
    outcome: Decimal
    difference: Decimal
    percent: Decimal
    direction: Direction


@dataclass(frozen=True)
class RangeCheck:
    low: Decimal
    high: Decimal
    point: Decimal

    @property
    def inside(self) -> bool:
        return self.low <= self.point <= self.high


@dataclass(frozen=True)
class BiasIndicator:
    """All retrospective differences point the same way: a possible bias (AU-C 540.A133)."""

    direction: Direction | None
    count: int

    @property
    def consistent(self) -> bool:
        return self.direction in ("over", "under") and self.count >= 2


def foot(components: Sequence[Decimal], balance: Decimal) -> Footing:
    total = sum(components, _ZERO)
    return Footing(total, balance, total - balance)


def rollforward(
    opening: Decimal, usage: Decimal, additions: Decimal, balance: Decimal
) -> Rollforward:
    return Rollforward(opening, usage, additions, opening - usage + additions, balance)


def percent_of(part: Decimal, whole: Decimal) -> Decimal:
    if whole == _ZERO:
        raise ValueError("a percentage of zero is undefined")
    return (part / whole * 100).quantize(_TENTH, rounding=ROUND_HALF_UP)


def retrospective(label: str, prior_estimate: Decimal, outcome: Decimal) -> Retrospective:
    """Over: the estimate exceeded what happened; under: it fell short."""
    signed = prior_estimate - outcome
    difference = abs(signed)
    direction: Direction = "exact" if signed == _ZERO else ("over" if signed > _ZERO else "under")
    return Retrospective(
        label,
        prior_estimate,
        outcome,
        difference,
        percent_of(difference, prior_estimate),
        direction,
    )


def range_check(low: Decimal, high: Decimal, point: Decimal) -> RangeCheck:
    if low > high:
        raise ValueError("an auditor range runs low to high")
    return RangeCheck(low, high, point)


def bias(retrospectives: Sequence[Retrospective]) -> BiasIndicator:
    directions: set[Direction] = {r.direction for r in retrospectives if r.direction != "exact"}
    if len(directions) == 1:
        only: Direction = next(iter(directions))
        return BiasIndicator(only, sum(1 for r in retrospectives if r.direction == only))
    return BiasIndicator(None, 0)
