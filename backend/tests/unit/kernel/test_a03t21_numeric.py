"""A-03-T21 (SPEC-580 AC-4): kernel.numeric, the shared Decimal context and allocation."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

import pytest

from abacus.kernel import numeric
from abacus.kernel.numeric import allocate, quantize_half_up, unit


def test_ac4_the_context_is_precision_28_half_up() -> None:
    assert numeric.PRECISION == 28
    assert numeric.CONTEXT.prec == 28
    assert numeric.CONTEXT.rounding == ROUND_HALF_UP


@pytest.mark.parametrize(
    ("value", "places", "expected"),
    [
        ("2.345", 2, "2.35"),
        ("-2.345", 2, "-2.35"),
        ("2.344", 2, "2.34"),
        ("0.0875", 3, "0.088"),
        ("35267.2", 0, "35267"),
        ("0.5", 0, "1"),
    ],
)
def test_ac4_quantize_half_up_rounds_half_away_from_zero(
    value: str, places: int, expected: str
) -> None:
    assert quantize_half_up(Decimal(value), places) == Decimal(expected)


def test_ac4_largest_remainder_gives_the_leftover_cent_to_the_largest_remainder() -> None:
    # 100.00 in thirds: 33.33 each and one cent left, which goes to the first (ties by order).
    assert allocate(Decimal("100.00"), [Decimal(1)] * 3) == (
        Decimal("33.34"),
        Decimal("33.33"),
        Decimal("33.33"),
    )
    # 10.00 split 1:2:3 → 1.666…, 3.333…, 5.000 → 1.67, 3.33, 5.00.
    assert allocate(Decimal("10.00"), [Decimal(1), Decimal(2), Decimal(3)]) == (
        Decimal("1.67"),
        Decimal("3.33"),
        Decimal("5.00"),
    )


def test_ac4_half_up_shares_put_the_difference_on_the_largest_weight() -> None:
    # 1.00 by thirds rounds each to 0.33; the missing cent lands on the largest (first) weight.
    assert allocate(Decimal("1.00"), [Decimal(1)] * 3, half_up_shares=True) == (
        Decimal("0.34"),
        Decimal("0.33"),
        Decimal("0.33"),
    )
    shares = allocate(Decimal("1.00"), [Decimal(1), Decimal(5), Decimal(1)], half_up_shares=True)
    assert sum(shares) == Decimal("1.00")


def test_ac4_a_negative_total_splits_its_magnitude_and_negates() -> None:
    assert allocate(Decimal("-100.00"), [Decimal(1)] * 3) == (
        Decimal("-33.34"),
        Decimal("-33.33"),
        Decimal("-33.33"),
    )


def test_ac4_whole_units() -> None:
    assert allocate(Decimal(7), [Decimal(1), Decimal(1)], 0) == (Decimal(4), Decimal(3))
    assert unit(0) == Decimal(1)
    assert unit(2) == Decimal("0.01")


@pytest.mark.parametrize(
    ("total", "weights", "places"),
    [
        (Decimal("1.00"), [], 2),
        (Decimal("1.00"), [Decimal(-1), Decimal(2)], 2),
        (Decimal("1.00"), [Decimal(0), Decimal(0)], 2),
        (Decimal("1.005"), [Decimal(1)], 2),
        (Decimal("1.00"), [Decimal(1)], -1),
    ],
)
def test_ac4_invalid_inputs_are_refused(
    total: Decimal, weights: list[Decimal], places: int
) -> None:
    with pytest.raises(ValueError):
        allocate(total, weights, places)
