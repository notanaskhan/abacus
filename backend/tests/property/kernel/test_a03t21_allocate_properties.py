"""A-03-T21 (SPEC-580 AC-4): every split foots, whatever the weights (Hypothesis)."""

from __future__ import annotations

from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from abacus.kernel.numeric import allocate, unit

_cents = st.integers(min_value=-(10**12), max_value=10**12).map(lambda c: Decimal(c).scaleb(-2))
_weights = st.lists(
    st.decimals(min_value=0, max_value=10**9, places=4, allow_nan=False, allow_infinity=False),
    min_size=1,
    max_size=40,
).filter(lambda ws: sum(ws) > 0)


@settings(max_examples=300, deadline=None)
@given(total=_cents, weights=_weights, half_up=st.booleans())
def test_ac4_every_split_foots_to_the_total(
    total: Decimal, weights: list[Decimal], half_up: bool
) -> None:
    shares = allocate(total, weights, 2, half_up_shares=half_up)
    assert len(shares) == len(weights)
    assert sum(shares, Decimal(0)) == total
    for share in shares:
        assert share == share.quantize(unit(2))


@settings(max_examples=200, deadline=None)
@given(total=_cents, weights=_weights)
def test_ac4_largest_remainder_is_never_more_than_one_step_from_exact(
    total: Decimal, weights: list[Decimal]
) -> None:
    shares = allocate(total, weights, 2)
    weight_sum = sum(weights, Decimal(0))
    for share, weight in zip(shares, weights, strict=True):
        exact = total * weight / weight_sum
        assert abs(share - exact) < unit(2)


@settings(max_examples=100, deadline=None)
@given(total=_cents, weights=_weights)
def test_ac4_a_zero_weight_gets_nothing_by_largest_remainder(
    total: Decimal, weights: list[Decimal]
) -> None:
    shares = allocate(total, [*weights, Decimal(0)], 2)
    assert shares[-1] == 0
