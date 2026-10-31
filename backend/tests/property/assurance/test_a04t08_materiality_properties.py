"""A-04-T08: materiality engine properties (Hypothesis): every output sits on the increment, PM
and CT never exceed the overall, the hash is deterministic, and the policy holds."""

from __future__ import annotations

from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from abacus.modules.assurance.compute import materiality as m

D = Decimal
EBP = m.Policy(D("1.0"), D("2.0"), D("50"), D("75"), D("5"))

_amounts = st.integers(min_value=10_000, max_value=10**12).map(D)
_rates = st.decimals(min_value="1.0", max_value="2.0", places=2)
_pms = st.decimals(min_value="50", max_value="75", places=1)


def _t(amount: Decimal, rate: Decimal, pm: Decimal) -> m.Thresholds:
    return m.thresholds(
        basis="unadjusted",
        benchmark_key="net_assets",
        benchmark_amount=amount,
        rate_pct=rate,
        pm_pct=pm,
        ct_pct=D("5"),
        policy=EBP,
    )


@settings(max_examples=300, deadline=None)
@given(amount=_amounts, rate=_rates, pm=_pms)
def test_overall_on_the_increment_and_shares_whole_dollars(
    amount: Decimal, rate: Decimal, pm: Decimal
) -> None:
    t = _t(amount, rate, pm)
    assert t.overall % 100 == 0
    assert abs(t.overall - amount * rate / 100) <= 50
    assert t.pm == t.pm.to_integral_value() and t.ct == t.ct.to_integral_value()
    assert t.ct <= t.pm <= t.overall


@settings(max_examples=200, deadline=None)
@given(amount=_amounts, rate=_rates, pm=_pms)
def test_same_inputs_same_figures_and_hash(amount: Decimal, rate: Decimal, pm: Decimal) -> None:
    assert _t(amount, rate, pm) == _t(amount, rate, pm)


@settings(max_examples=200, deadline=None)
@given(amount=_amounts, low=_amounts, rate=_rates)
def test_overall_is_monotonic_in_the_benchmark(
    amount: Decimal, low: Decimal, rate: Decimal
) -> None:
    small, big = sorted((amount, low))
    assert _t(small, rate, D("75")).overall <= _t(big, rate, D("75")).overall


@settings(max_examples=200, deadline=None)
@given(amount=_amounts, final=_amounts, rate=_rates)
def test_reassessment_difference_foots(amount: Decimal, final: Decimal, rate: Decimal) -> None:
    decided = _t(amount, rate, D("75"))
    r = m.reassess(decided, final_amount=final)
    assert r.at_rate - decided.overall == r.difference
    assert r.at_rate % 100 == 0
