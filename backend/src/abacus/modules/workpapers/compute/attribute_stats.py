"""Attribute sampling statistics for a test's deviation log (A-08-T14; A-08 §3 F2; AU-C 530;
ADR-050). Pure: Decimal only, no clock, no I/O.

The upper deviation limit (UDL) is the exact (Clopper-Pearson) one-sided upper bound on the
population deviation rate: the rate p at which seeing at most `deviations` in `sample_size`
draws has probability 1 - confidence. Solved by bisection in Decimal to 1e-9 and shown to one
decimal place, half up (0 of 25 at 90% reads 8.8%).
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, localcontext
from math import comb
from typing import Final

ENGINE_VERSION: Final = "attribute_stats/1"
_TENTH: Final = Decimal("0.1")
_EPS: Final = Decimal("1e-9")


class StatsInvalid(ValueError):
    code = "attribute_stats_invalid"


def _at_most(deviations: int, sample_size: int, rate: Decimal) -> Decimal:
    """P(X <= deviations) for X ~ Binomial(sample_size, rate)."""
    total = Decimal(0)
    for k in range(deviations + 1):
        total += Decimal(comb(sample_size, k)) * rate**k * (1 - rate) ** (sample_size - k)
    return total


def upper_deviation_limit(deviations: int, sample_size: int, confidence: Decimal) -> Decimal:
    """The UDL as a percent to one decimal place (100.0 when every item deviated)."""
    if sample_size < 1 or not 0 <= deviations <= sample_size:
        raise StatsInvalid("deviations between 0 and the sample size")
    if not Decimal(0) < confidence < Decimal(1):
        raise StatsInvalid("confidence is a fraction")
    if deviations == sample_size:
        return Decimal("100.0")
    with localcontext() as ctx:
        ctx.prec = 40
        target = 1 - Decimal(confidence)
        low, high = Decimal(deviations) / sample_size, Decimal(1)
        while high - low > _EPS:
            mid = (low + high) / 2
            if _at_most(deviations, sample_size, mid) > target:
                low = mid
            else:
                high = mid
        return (high * 100).quantize(_TENTH, rounding=ROUND_HALF_UP)


def below_clearly_trivial(difference: Decimal, clearly_trivial: Decimal) -> bool:
    """A difference strictly below CT in absolute value is logged, never an exception."""
    return abs(Decimal(difference)) < Decimal(clearly_trivial)
