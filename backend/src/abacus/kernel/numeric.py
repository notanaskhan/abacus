"""Money and rate arithmetic for the compute packages (A-03-T21; chapter 03 §10.1; ADR-050).

One Decimal context (precision 28, ROUND_HALF_UP) that every compute package shares, a half-up
quantizer, and `allocate`: a total split by weights so the shares always foot to the total.

Pure: no clock, no database, no I/O, and no import of any module. `sampling/compute` and
`ledger/compute` may import only this and `kernel.calendar` (the import-linter contract in
`backend/pyproject.toml`).
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Context, Decimal, localcontext
from typing import Final

PRECISION: Final = 28
CONTEXT: Final = Context(prec=PRECISION, rounding=ROUND_HALF_UP)


def unit(places: int) -> Decimal:
    """The smallest step at `places` decimals: 0.01 for 2, 1 for 0."""
    if places < 0:
        raise ValueError("places must not be negative")
    return Decimal(1).scaleb(-places)


def quantize_half_up(value: Decimal, places: int) -> Decimal:
    """`value` rounded half away from zero to `places` decimals (2.345 → 2.35, -2.345 → -2.35)."""
    with localcontext(CONTEXT):
        return value.quantize(unit(places), rounding=ROUND_HALF_UP)


def allocate(
    total: Decimal,
    weights: Sequence[Decimal],
    places: int = 2,
    *,
    half_up_shares: bool = False,
) -> tuple[Decimal, ...]:
    """Split `total` by `weights` into shares at `places` decimals that sum exactly to `total`.

    Largest remainder (the default): every share is floored to the step, then the steps left over
    go one each to the shares with the largest remainders, the earlier share first on a tie.
    `half_up_shares=True` rounds every share half up instead and puts the rounding difference on
    the share with the largest weight (the earliest on a tie), for allocations whose policy says
    each share is rounded on its own.

    `total` must already be at `places` decimals; weights must be non-negative with a positive sum.
    A negative total is split as its magnitude and every share negated.
    """
    step = unit(places)
    if not weights:
        raise ValueError("weights must not be empty")
    if any(weight < 0 for weight in weights):
        raise ValueError("weights must not be negative")
    with localcontext(CONTEXT):
        weight_sum = sum(weights, Decimal(0))
        if weight_sum == 0:
            raise ValueError("weights must not all be zero")
        if total.quantize(step, rounding=ROUND_HALF_UP) != total:
            raise ValueError("total must be at the allocation's places")
        sign = -1 if total < 0 else 1
        magnitude = abs(total)
        exact = [magnitude * weight / weight_sum for weight in weights]
        if half_up_shares:
            shares = [share.quantize(step, rounding=ROUND_HALF_UP) for share in exact]
            largest = max(range(len(weights)), key=lambda i: (weights[i], -i))
            shares[largest] += magnitude - sum(shares, Decimal(0))
        else:
            shares = [share.quantize(step, rounding=ROUND_FLOOR) for share in exact]
            left = int((magnitude - sum(shares, Decimal(0))) / step)
            order = sorted(range(len(weights)), key=lambda i: (-(exact[i] - shares[i]), i))
            for i in order[:left]:
                shares[i] += step
        return tuple(share * sign if sign < 0 else share for share in shares)
