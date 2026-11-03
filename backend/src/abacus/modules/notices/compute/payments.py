"""Payment footing (N-04 US-4.3): the notice's tax, interest and penalty foot to its total.

Interest and penalty are the notice's figures and are never recomputed (QN-3).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, localcontext

from abacus.kernel.numeric import CONTEXT, quantize_half_up
from abacus.modules.notices.compute.stamp import Stamp, stamp


@dataclass(frozen=True)
class Footing:
    computed_total: Decimal
    foots: bool
    difference: Decimal
    stamp: Stamp


def foot(
    tax: Decimal | None, interest: Decimal | None, penalty: Decimal | None, total: Decimal | None
) -> Footing:
    with localcontext(CONTEXT):
        computed = quantize_half_up(
            sum((v or Decimal(0) for v in (tax, interest, penalty)), Decimal(0)), 2
        )
        difference = quantize_half_up((total or Decimal(0)) - computed, 2)
    return Footing(
        computed,
        total is not None and difference == 0,
        difference,
        stamp(
            "payments.foot", {"tax": tax, "interest": interest, "penalty": penalty, "total": total}
        ),
    )
