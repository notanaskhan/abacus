"""Attribute sample size, upper deviation limit and projection, by code (ADR-340 §6; A-03-T04;
SPEC-580 AC-8).

- `attribute_size`: the statistical cross-check beside the firm's size table (the table itself is
  firm content, K-02's `attribute_sample_sizes` policy). The smallest n for which allowing
  floor(n x expected rate) deviations still gives at most a (1 - confidence) chance of seeing that
  few when the true rate is the tolerable rate: 22 at 90% confidence, 10% tolerable, 0% expected.
- `udl`: the exact binomial (Clopper-Pearson) upper deviation limit, solved by bisection in the
  shared Decimal context: 8.8% for 0 of 25 and 19.9% for 2 of 25 at 90%.
- `project` and `project_ratio`: misstatement projected to the population, by count or by amount.

Inputs are taken as Decimal through `str()`, so 0.90 means 0.90 and never 0.9000000000000000222.
"""

from __future__ import annotations

from decimal import Decimal, localcontext
from math import comb
from typing import Final

from abacus.kernel.numeric import CONTEXT, quantize_half_up

Number = Decimal | int | float | str
_BISECTIONS: Final = 120
_MAX_SIZE: Final = 100_000


def _dec(value: Number) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _rate(value: Number, name: str, *, open_low: bool = False) -> Decimal:
    rate = _dec(value)
    if not (Decimal(0) < rate < Decimal(1) if open_low else Decimal(0) <= rate < Decimal(1)):
        raise ValueError(f"{name} must lie in {'(0, 1)' if open_low else '[0, 1)'}")
    return rate


def binomial_cdf(k: int, n: int, p: Decimal) -> Decimal:
    """P(X ≤ k) for X ~ Binomial(n, p), in the shared context."""
    with localcontext(CONTEXT):
        if k >= n:
            return Decimal(1)
        q = Decimal(1) - p
        return sum((comb(n, i) * p**i * q ** (n - i) for i in range(k + 1)), Decimal(0))


def attribute_size(confidence: Number, tolerable_rate: Number, expected_rate: Number = 0) -> int:
    """The statistical attribute sample size (smallest n; see the module note)."""
    conf = _rate(confidence, "confidence", open_low=True)
    tolerable = _rate(tolerable_rate, "tolerable_rate", open_low=True)
    expected = _rate(expected_rate, "expected_rate")
    if expected >= tolerable:
        raise ValueError("the expected rate must be below the tolerable rate")
    risk = Decimal(1) - conf
    with localcontext(CONTEXT):
        for n in range(1, _MAX_SIZE + 1):
            allowed = int(n * expected)
            if binomial_cdf(allowed, n, tolerable) <= risk:
                return n
    raise ValueError("no sample size up to 100,000 meets these parameters")


def udl(deviations: int, size: int, confidence: Number) -> Decimal:
    """The upper deviation limit as a rate.

    The p where P(X <= deviations | size, p) = 1 - confidence (Clopper-Pearson).
    """
    if size <= 0 or not 0 <= deviations <= size:
        raise ValueError("deviations must lie between 0 and a positive size")
    risk = Decimal(1) - _rate(confidence, "confidence", open_low=True)
    if deviations == size:
        return Decimal(1)
    with localcontext(CONTEXT):
        low, high = Decimal(0), Decimal(1)
        for _ in range(_BISECTIONS):
            middle = (low + high) / 2
            if binomial_cdf(deviations, size, middle) > risk:
                low = middle
            else:
                high = middle
        return high


def udl_percent(deviations: int, size: int, confidence: Number) -> Decimal:
    """The limit as the screens show it: a percentage to one decimal, half up (8.8, 19.9)."""
    return quantize_half_up(udl(deviations, size, confidence) * 100, 1)


def project(misstatement: Number, sample_count: int, population_count: int) -> Decimal:
    """Projected misstatement by count: 2,140 in 25 of 412 is 35,267.20 (QA-3: display open)."""
    if sample_count <= 0 or population_count < sample_count:
        raise ValueError("the sample must be a non-empty part of the population")
    with localcontext(CONTEXT):
        return quantize_half_up(_dec(misstatement) * population_count / sample_count, 2)


def project_ratio(
    misstatement: Number, sample_amount: Number, population_amount: Number
) -> Decimal:
    """Projected misstatement by amount (ratio estimate): misstatement x population ÷ sample."""
    sample = _dec(sample_amount)
    if sample <= 0:
        raise ValueError("the sample amount must be positive")
    with localcontext(CONTEXT):
        return quantize_half_up(_dec(misstatement) * _dec(population_amount) / sample, 2)
