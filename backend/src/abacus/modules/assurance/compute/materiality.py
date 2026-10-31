"""The materiality engine (A-04-T08; A-04 §3.3 AC3.1-AC3.3, AC3.6, AC3.8; ADR-050; DEC-1850).

Pure: Decimal only, no clock, no database, no I/O. The caller (the A-04-T12 service) reads the
benchmark totals from C9 at the Unadjusted or Final layer and the firm range from
`methodology.api.materiality_range_for`, and passes them in as plain values; every result carries
`ENGINE_NAME`, `ENGINE_VERSION` and the SHA-256 `inputs_hash` of its canonical inputs, so a
re-performer with the same inputs gets the same figures and the same hash.

The arithmetic, as the AUD-07 handoff writes it:

- overall = benchmark x rate, rounded to the policy increment (default 100) half up:
  16,812,400 x 1.5% = 252,186 -> 252,200;
- PM and CT from the rounded overall, to the whole dollar half up: 75% = 189,150, 5% = 12,610;
- a benchmark's range: low and high rounded the same way (1,318,300 at 3.0%-5.0% -> 39,500 and
  65,900);
- prior years at the rate (14,228,500 x 1.5% -> 213,400) and growth on the first prior year to one
  decimal (16,812,400 / 14,228,500 - 1 = 18.2%);
- the final basis at the decided rate and its difference from the decided overall, the percent to
  one decimal (16,861,000 -> 252,900; +700; 0.3%).

The engine refuses a rate, PM or CT outside the firm's policy (`OutsidePolicy`; the service answers
409 `outside_policy`); it never chooses: the options are the bottom of the firm range and its
midpoint, and the engagement partner decides (INV-1).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, localcontext
from typing import Final, Literal

from abacus.kernel.numeric import CONTEXT, quantize_half_up

ENGINE_NAME: Final = "materiality"
ENGINE_VERSION: Final = "1"
DEFAULT_INCREMENT: Final = Decimal(100)

Basis = Literal["unadjusted", "final"]

_HUNDRED: Final = Decimal(100)
_ZERO: Final = Decimal(0)


class MaterialityInvalid(ValueError):
    """An input the engine cannot use (a non-positive benchmark or increment, a bad percent)."""

    code = "materiality_invalid"


class OutsidePolicy(ValueError):
    """A rate, PM or CT outside the firm's policy; `field` names which (AC3.3)."""

    code = "outside_policy"

    def __init__(self, field_name: str) -> None:
        super().__init__(f"{field_name} is outside the firm's materiality policy")
        self.field = field_name


@dataclass(frozen=True)
class Policy:
    """The firm's range for one engagement kind (K-02 `materiality_ranges`, inclusive bounds)."""

    low_pct: Decimal
    high_pct: Decimal
    pm_low_pct: Decimal
    pm_high_pct: Decimal
    ct_pct: Decimal
    increment: Decimal = DEFAULT_INCREMENT


@dataclass(frozen=True)
class Stamp:
    engine_name: str
    engine_version: str
    inputs_hash: str


@dataclass(frozen=True)
class Thresholds:
    basis: Basis
    benchmark_key: str
    benchmark_amount: Decimal
    rate_pct: Decimal
    overall: Decimal
    pm_pct: Decimal
    pm: Decimal
    ct_pct: Decimal
    ct: Decimal
    policy_low_pct: Decimal
    policy_high_pct: Decimal
    stamp: Stamp


@dataclass(frozen=True)
class PriorYear:
    """An audited prior-year amount; `overall_used` is that year's final overall, as recorded."""

    year: str
    amount: Decimal
    overall_used: Decimal | None = None


@dataclass(frozen=True)
class BenchmarkInput:
    key: str
    label: str
    amount: Decimal
    low_pct: Decimal
    high_pct: Decimal
    use: Literal["overall", "specific", "considered_for_specific", "not_used"]
    prior_years: tuple[PriorYear, ...] = ()


@dataclass(frozen=True)
class PriorYearAtRate:
    year: str
    amount: Decimal
    at_rate: Decimal
    overall_used: Decimal | None


@dataclass(frozen=True)
class Benchmark:
    key: str
    label: str
    amount: Decimal
    range_low_pct: Decimal
    range_high_pct: Decimal
    low: Decimal
    high: Decimal
    use: str
    prior_years: tuple[PriorYearAtRate, ...]
    growth_pct: Decimal | None
    stamp: Stamp


@dataclass(frozen=True)
class Option:
    """A card option. `thresholds` is None for "custom" (the partner types a rate in range)."""

    key: str
    thresholds: Thresholds | None


@dataclass(frozen=True)
class Reassessment:
    final_amount: Decimal
    at_rate: Decimal
    difference: Decimal
    difference_pct: Decimal
    stamp: Stamp


def _stamp(**parts: object) -> Stamp:
    """The engine stamp: SHA-256 over the canonical inputs, keys sorted, Decimals by value."""
    body = json.dumps(
        {
            "engine": ENGINE_NAME,
            "version": ENGINE_VERSION,
            **{k: _text(v) for k, v in parts.items()},
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return Stamp(ENGINE_NAME, ENGINE_VERSION, hashlib.sha256(body.encode("utf-8")).hexdigest())


def _text(value: object) -> object:
    """Decimals hash by value, not by spelling: 1.5, 1.50 and 1.500 are one input."""
    if isinstance(value, Decimal):
        normal = value.normalize(CONTEXT)
        return format(normal, "f")
    if isinstance(value, (list, tuple)):
        return [_text(v) for v in value]
    return value


def _money(value: Decimal) -> Decimal:
    return quantize_half_up(value, 2)


def _check_pct(name: str, pct: Decimal) -> None:
    if not pct.is_finite() or not _ZERO < pct <= _HUNDRED:
        raise MaterialityInvalid(name)


def _check_amount(name: str, amount: Decimal) -> None:
    if not amount.is_finite() or amount <= _ZERO:
        raise MaterialityInvalid(name)


def round_to_increment(value: Decimal, increment: Decimal = DEFAULT_INCREMENT) -> Decimal:
    """`value` to the nearest `increment`, half up (252,186 -> 252,200; 24,379.5 -> 24,400)."""
    _check_amount("increment", increment)
    with localcontext(CONTEXT):
        steps = (value / increment).quantize(Decimal(1), rounding=ROUND_HALF_UP)
        return _money(steps * increment)


def at_rate(amount: Decimal, rate_pct: Decimal, increment: Decimal = DEFAULT_INCREMENT) -> Decimal:
    """`amount` x `rate_pct`%, rounded to the increment half up."""
    with localcontext(CONTEXT):
        return round_to_increment(amount * rate_pct / _HUNDRED, increment)


def _share(overall: Decimal, pct: Decimal) -> Decimal:
    """A share of the rounded overall to the whole dollar, half up (PM and CT)."""
    with localcontext(CONTEXT):
        return _money(quantize_half_up(overall * pct / _HUNDRED, 0))


def check_policy(policy: Policy, *, rate_pct: Decimal, pm_pct: Decimal, ct_pct: Decimal) -> None:
    """Refuse a rate, PM or CT outside the firm's policy (AC3.3); bounds are inclusive."""
    for name, pct in (("rate_pct", rate_pct), ("pm_pct", pm_pct), ("ct_pct", ct_pct)):
        _check_pct(name, pct)
    if not policy.low_pct <= rate_pct <= policy.high_pct:
        raise OutsidePolicy("rate_pct")
    if not policy.pm_low_pct <= pm_pct <= policy.pm_high_pct:
        raise OutsidePolicy("pm_pct")
    if ct_pct != policy.ct_pct:
        raise OutsidePolicy("ct_pct")


def thresholds(
    *,
    basis: Basis,
    benchmark_key: str,
    benchmark_amount: Decimal,
    rate_pct: Decimal,
    pm_pct: Decimal,
    ct_pct: Decimal,
    policy: Policy,
) -> Thresholds:
    """Overall, PM and CT by code, inside the policy (AC3.1, AC3.8)."""
    _check_amount("benchmark_amount", benchmark_amount)
    check_policy(policy, rate_pct=rate_pct, pm_pct=pm_pct, ct_pct=ct_pct)
    overall = at_rate(benchmark_amount, rate_pct, policy.increment)
    stamp = _stamp(
        kind="thresholds",
        basis=basis,
        benchmark_key=benchmark_key,
        benchmark_amount=benchmark_amount,
        rate_pct=rate_pct,
        pm_pct=pm_pct,
        ct_pct=ct_pct,
        policy=[policy.low_pct, policy.high_pct, policy.pm_low_pct, policy.pm_high_pct],
        policy_ct=policy.ct_pct,
        increment=policy.increment,
    )
    return Thresholds(
        basis=basis,
        benchmark_key=benchmark_key,
        benchmark_amount=_money(benchmark_amount),
        rate_pct=rate_pct,
        overall=overall,
        pm_pct=pm_pct,
        pm=_share(overall, pm_pct),
        ct_pct=ct_pct,
        ct=_share(overall, ct_pct),
        policy_low_pct=policy.low_pct,
        policy_high_pct=policy.high_pct,
        stamp=stamp,
    )


def preview(
    *,
    basis: Basis,
    benchmark_key: str,
    benchmark_amount: Decimal,
    rate_pct: Decimal,
    pm_pct: Decimal,
    ct_pct: Decimal,
    policy: Policy,
) -> Thresholds:
    """The slider and the PM/CT steppers (AC3.3): the same figures as `thresholds`, written
    nowhere; the browser does no arithmetic."""
    return thresholds(
        basis=basis,
        benchmark_key=benchmark_key,
        benchmark_amount=benchmark_amount,
        rate_pct=rate_pct,
        pm_pct=pm_pct,
        ct_pct=ct_pct,
        policy=policy,
    )


def growth_pct(current: Decimal, prior: Decimal) -> Decimal | None:
    """current / prior - 1 as a percent, one decimal half up; None for a prior of zero or less."""
    if prior <= _ZERO:
        return None
    with localcontext(CONTEXT):
        return quantize_half_up((current / prior - 1) * _HUNDRED, 1)


def benchmark(
    item: BenchmarkInput, *, rate_pct: Decimal, increment: Decimal = DEFAULT_INCREMENT
) -> Benchmark:
    """A statement row: the range's low and high, prior years at `rate_pct` and growth (AC3.2).

    `rate_pct` is the rate the prior years are shown at (the proposed overall's); prior years never
    change today's thresholds.
    """
    _check_amount("benchmark_amount", item.amount)
    _check_pct("low_pct", item.low_pct)
    _check_pct("high_pct", item.high_pct)
    _check_pct("rate_pct", rate_pct)
    if item.low_pct > item.high_pct:
        raise MaterialityInvalid("range")
    priors = tuple(
        PriorYearAtRate(
            p.year,
            _money(p.amount),
            at_rate(p.amount, rate_pct, increment),
            None if p.overall_used is None else _money(p.overall_used),
        )
        for p in item.prior_years
    )
    first = item.prior_years[0].amount if item.prior_years else None
    stamp = _stamp(
        kind="benchmark",
        key=item.key,
        amount=item.amount,
        range=[item.low_pct, item.high_pct],
        rate_pct=rate_pct,
        increment=increment,
        prior_years=[[p.year, p.amount, p.overall_used] for p in item.prior_years],
    )
    return Benchmark(
        key=item.key,
        label=item.label,
        amount=_money(item.amount),
        range_low_pct=item.low_pct,
        range_high_pct=item.high_pct,
        low=at_rate(item.amount, item.low_pct, increment),
        high=at_rate(item.amount, item.high_pct, increment),
        use=item.use,
        prior_years=priors,
        growth_pct=None if first is None else growth_pct(item.amount, first),
        stamp=stamp,
    )


def option_rates(policy: Policy) -> tuple[Decimal, ...]:
    """The code-computed option set: the bottom of the firm range and its midpoint (1.0% and 1.5%
    for 1.0%-2.0%; 3% and 5% for 3%-7%). The partner may also type any rate in range."""
    with localcontext(CONTEXT):
        mid = (policy.low_pct + policy.high_pct) / 2
    return (policy.low_pct,) if mid == policy.low_pct else (policy.low_pct, mid)


def option_key(rate_pct: Decimal) -> str:
    """ "rate_1_0" for 1.0%, "rate_1_5" for 1.5%, "rate_5_0" for 5% (one decimal, half up)."""
    whole, _, tenth = format(quantize_half_up(rate_pct, 1), "f").partition(".")
    return f"rate_{whole}_{tenth or '0'}"


def options(
    *,
    basis: Basis,
    benchmark_key: str,
    benchmark_amount: Decimal,
    pm_pct: Decimal,
    ct_pct: Decimal,
    policy: Policy,
) -> tuple[Option, ...]:
    """The card's options, each with its thresholds, then "custom" (AC3.1, AC3.4)."""
    computed = tuple(
        Option(
            option_key(rate),
            thresholds(
                basis=basis,
                benchmark_key=benchmark_key,
                benchmark_amount=benchmark_amount,
                rate_pct=rate,
                pm_pct=pm_pct,
                ct_pct=ct_pct,
                policy=policy,
            ),
        )
        for rate in option_rates(policy)
    )
    return (*computed, Option("custom", None))


def option_keys(policy: Policy) -> frozenset[str]:
    """Every key a recommendation may name (A-04-T09's "option key in the code set" grader)."""
    return frozenset({*(option_key(r) for r in option_rates(policy)), "custom"})


def reassess(
    decided: Thresholds, *, final_amount: Decimal, increment: Decimal | None = None
) -> Reassessment:
    """The final basis at the decided rate and its difference from the decided overall (AC3.6).

    The difference is signed (final minus decided); its percent is of the decided overall, to one
    decimal half up. Nothing is revised here: the partner records No change or Revise.
    """
    _check_amount("final_amount", final_amount)
    step = DEFAULT_INCREMENT if increment is None else increment
    final_overall = at_rate(final_amount, decided.rate_pct, step)
    difference = final_overall - decided.overall
    with localcontext(CONTEXT):
        pct = quantize_half_up(difference / decided.overall * _HUNDRED, 1)
    stamp = _stamp(
        kind="reassessment",
        decided=decided.stamp.inputs_hash,
        final_amount=final_amount,
        rate_pct=decided.rate_pct,
        increment=step,
    )
    return Reassessment(_money(final_amount), final_overall, _money(difference), pct, stamp)


def benchmarks(
    items: Sequence[BenchmarkInput], *, rate_pct: Decimal, increment: Decimal = DEFAULT_INCREMENT
) -> tuple[Benchmark, ...]:
    """Every benchmark row in the caller's order; exactly one row may be the overall's."""
    if sum(1 for i in items if i.use == "overall") > 1:
        raise MaterialityInvalid("overall_benchmark")
    if len({i.key for i in items}) != len(items):
        raise MaterialityInvalid("benchmark_key")
    return tuple(benchmark(i, rate_pct=rate_pct, increment=increment) for i in items)
