"""The balance-due comparison (CP14, CP501, CP503, CP504; N-04 US-4.5): the notice's amounts
beside the return's tax, payments and balance due, and the difference, by code."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, localcontext

from abacus.kernel.numeric import CONTEXT, quantize_half_up
from abacus.modules.notices.compute.stamp import Stamp, stamp


@dataclass(frozen=True)
class BalanceDue:
    return_balance: Decimal  # the return's tax less its payments
    notice_tax: Decimal  # the notice's tax due (before interest and penalty)
    difference: Decimal  # the notice's tax due less the return's balance
    agrees: bool
    stamp: Stamp


def compare(return_tax: Decimal, return_payments: Decimal, notice_tax: Decimal) -> BalanceDue:
    with localcontext(CONTEXT):
        balance = quantize_half_up(return_tax - return_payments, 2)
        difference = quantize_half_up(notice_tax - balance, 2)
    return BalanceDue(
        balance,
        notice_tax,
        difference,
        difference == 0,
        stamp(
            "balance_due.compare",
            {"tax": return_tax, "payments": return_payments, "notice_tax": notice_tax},
        ),
    )
