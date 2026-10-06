"""The common ledger model and trial balance validation (ADR-038, ADR-050). PROTECTED.
TASK-010 design §5 stage 4, revision 1.

Provider parsers (the fake format: `connections/fake_format.py`) produce this model; validation
here is provider-neutral. Code computes totals and checks them; nothing here is judged by a model.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import date
from decimal import Decimal


class NormaliseError(Exception):
    """A payload isn't a well-formed trial balance; `code` is recorded on the sync run."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class LedgerLine:
    """A trial balance line in the common ledger model, with its provider identifier."""

    account_code: str
    account_name: str
    debit: Decimal
    credit: Decimal
    source_ref: str


@dataclass(frozen=True)
class NormalisedTrialBalance:
    period_start: date
    period_end: date
    currency: str
    lines: tuple[LedgerLine, ...]
    declared_debit: Decimal
    declared_credit: Decimal

    @property
    def total_debit(self) -> Decimal:
        return sum((line.debit for line in self.lines), Decimal(0))

    @property
    def total_credit(self) -> Decimal:
        return sum((line.credit for line in self.lines), Decimal(0))


def _identity(text: str) -> str:
    """Codes that render alike are the same account: compatibility-normalised and case-folded."""
    return unicodedata.normalize("NFKC", text).casefold()


def validate(tb: NormalisedTrialBalance, *, period_start: date, period_end: date) -> str | None:
    """None if the trial balance may be used; otherwise the failure code (ADR-038). Checks run in
    a fixed order, so the code is stable for the same input."""
    if not tb.lines:
        return "empty"
    if (tb.period_start, tb.period_end) != (period_start, period_end):
        return "period_mismatch"
    if tb.currency != "USD":
        return "unsupported_currency"
    codes = [_identity(line.account_code) for line in tb.lines]
    if len(set(codes)) != len(codes):
        return "duplicate_account"
    refs = [line.source_ref for line in tb.lines]
    if len(set(refs)) != len(refs):
        return "duplicate_source_ref"
    if (tb.total_debit, tb.total_credit) != (tb.declared_debit, tb.declared_credit):
        return "control_totals_mismatch"
    if tb.total_debit != tb.total_credit:
        return "unbalanced"
    if tb.total_debit == 0:
        return "zero_total"  # "balanced" by having nothing in it
    return None
