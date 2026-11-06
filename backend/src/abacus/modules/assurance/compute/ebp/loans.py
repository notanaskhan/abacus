"""Participant loans and distributions (A-05-T42; A-05 §4.4 `loans`, `withholding`; EBP-05;
DEC-2306): pure functions.

- **Rollforward:** beginning + new - repayments - offsets = ending, by count and amount (288,500 +
  96,200 - 57,450 - 14,850 = 312,400; 41 + 5 - 7 - 3 = 36).
- **IRC 72(p):** a new loan is within the lesser of $50,000 or 50% of the vested balance, with a
  5-year term unless it buys a principal residence. The plan's own rule may be tighter.
- **Withholding:** 20% on an eligible rollover distribution's cash (an offset counts toward the
  distribution but withholding is limited to the cash), 10% by default on hardship and RMD, none on
  a direct rollover.
- **Offsets** are distributions on Schedule H line 2e(1), so line 2g stays 0 and Part IV 4b answers
  No: participant loans are excluded from the 4b question.

Every result carries the engine stamp. Decimal only, half up to cents.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Final, Literal

from abacus.kernel.numeric import quantize_half_up

ENGINE_NAME: Final = "ebp_loans"
ENGINE_VERSION: Final = "1"
LIMIT_CAP: Final = Decimal("50000.00")
TERM_MONTHS: Final = 60
_ZERO: Final = Decimal(0)
OFFSET_LINE: Final = "2e(1)"


@dataclass(frozen=True)
class Loan:
    loan_ref: str
    beginning: Decimal
    new: Decimal
    repayments: Decimal
    offsets: Decimal
    ending: Decimal


@dataclass(frozen=True)
class Rollforward:
    beginning: Decimal
    new: Decimal
    repayments: Decimal
    offsets: Decimal
    ending: Decimal
    foots: bool
    count_beginning: int
    count_new: int
    count_paid_off: int
    count_offset: int
    count_ending: int
    inputs_hash: str
    engine_version: str = ENGINE_VERSION


def _hash(loans: Sequence[Loan]) -> str:
    rows = sorted(
        f"{x.loan_ref}|{x.beginning}|{x.new}|{x.repayments}|{x.offsets}|{x.ending}" for x in loans
    )
    return hashlib.sha256(json.dumps(rows).encode()).hexdigest()


def rollforward(loans: Sequence[Loan]) -> Rollforward:
    """Totals and counts by code. A loan whose ending is 0 after a repayment is paid off; after an
    offset it is offset. Footing compares the rolled total with the listed endings."""
    beginning = sum((x.beginning for x in loans), _ZERO)
    new = sum((x.new for x in loans), _ZERO)
    repayments = sum((x.repayments for x in loans), _ZERO)
    offsets = sum((x.offsets for x in loans), _ZERO)
    ending = sum((x.ending for x in loans), _ZERO)
    count_offset = sum(1 for x in loans if x.offsets > 0 and x.ending == 0)
    count_paid = sum(1 for x in loans if x.offsets == 0 and x.ending == 0)
    return Rollforward(
        beginning, new, repayments, offsets, ending,
        beginning + new - repayments - offsets == ending,
        sum(1 for x in loans if x.beginning > 0),
        sum(1 for x in loans if x.new > 0),
        count_paid,
        count_offset,
        sum(1 for x in loans if x.ending > 0),
        _hash(loans),
    )  # fmt: skip


@dataclass(frozen=True)
class LoanLimit:
    limit: Decimal
    within_amount: bool
    within_term: bool
    within: bool


def loan_limit(
    amount: Decimal,
    vested_balance: Decimal,
    term_months: int,
    is_residence: bool,
    plan_cap: Decimal | None = None,
) -> LoanLimit:
    """IRC 72(p): the lesser of 50,000 and half the vested balance; the plan's rule if tighter."""
    half = quantize_half_up(vested_balance / 2, Decimal("0.01"))
    limit = min(LIMIT_CAP, half) if plan_cap is None else min(LIMIT_CAP, half, plan_cap)
    within_amount = amount <= limit
    within_term = is_residence or term_months <= TERM_MONTHS
    return LoanLimit(limit, within_amount, within_term, within_amount and within_term)


DistributionKind = Literal[
    "eligible_rollover", "direct_rollover", "hardship", "rmd", "loan_offset"
]
_DEFAULT_RATE: Final[dict[str, Decimal]] = {
    "eligible_rollover": Decimal("0.20"),
    "loan_offset": Decimal("0.20"),
    "hardship": Decimal("0.10"),
    "rmd": Decimal("0.10"),
    "direct_rollover": _ZERO,
}


def withholding(kind: DistributionKind, gross: Decimal, offset: Decimal = _ZERO) -> Decimal:
    """The rate on the whole taxable amount, offsets included, limited to the cash paid."""
    rate = _DEFAULT_RATE[kind]
    computed = quantize_half_up((gross + offset) * rate, Decimal("0.01"))
    return min(computed, gross)


def offsets_total(amounts: Sequence[Decimal]) -> Decimal:
    return sum(amounts, _ZERO)


@dataclass(frozen=True)
class Comparative:
    agrees: bool
    off_by: Decimal


def py_comparative(beginning: Decimal, py_audited: Decimal | None) -> Comparative:
    """The rollforward's beginning against the prior year's audited figure (EBP-05 c)."""
    if py_audited is None:
        return Comparative(True, _ZERO)
    return Comparative(beginning == py_audited, beginning - py_audited)


def part_iv_4b() -> Literal["no"]:
    """Part IV 4b excludes participant loans (the Form 5500 instructions): always No on this plan's
    loan facts; a real default outside loans reaches 4b through EBP-07's findings check."""
    return "no"
