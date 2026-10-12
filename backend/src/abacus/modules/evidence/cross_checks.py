"""Ledger cross-checks for uploads (SPEC-029 goal 6; TASK-055 D3; ADR-050). PROTECTED.

Pure code. A document's total against the books at the year end, for the firm only (Q3: a
bank-to-books difference is often legitimate). Which account is "cash" or a control account is
read from the firm's methodology area names, or from account names when no methodology is
pinned, and never guessed beyond that: anything ambiguous is `not_applicable`.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Final

from abacus.modules.evidence.checks import CheckResult

_CASH: Final = re.compile(r"\b(?:cash|bank|checking|savings)\b", re.I)
_CASH_AREA: Final = re.compile(r"\b(?:cash|bank)\b", re.I)
# "Bank fees", "Interest income - bank", "Bank loan": named for a bank, not cash held in one.
_NOT_CASH: Final = re.compile(r"\b(?:fees?|charges?|interest|loans?|overdraft|expense)\b", re.I)
_RECEIVABLE: Final = re.compile(r"\b(?:accounts receivable|trade receivables?)\b", re.I)
_PAYABLE: Final = re.compile(r"\b(?:accounts payable|trade payables?)\b", re.I)
_ALLOWANCE: Final = re.compile(r"\b(?:allowance|provision|doubtful|reserve)\b", re.I)
CODE: Final = "ledger_cross_check"


@dataclass(frozen=True)
class Account:
    code: str
    name: str
    balance: Decimal  # debit minus credit
    area_name: str | None = None  # the methodology area it maps to, if any


def _na(reason: str) -> CheckResult:
    return CheckResult(CODE, "not_applicable", "firm", reason)


def _result(account_code: str, document: Decimal, book: Decimal) -> CheckResult:
    difference = document - book
    return CheckResult(
        CODE,
        "passed" if difference == 0 else "problem",
        "firm",
        amount=book,
        difference=difference,
        account_code=account_code[:40],
    )


def cash_accounts(accounts: Sequence[Account], has_methodology: bool) -> list[Account]:
    """In a methodology area named for cash or bank; with no methodology, accounts so named."""
    if has_methodology:
        return [a for a in accounts if a.area_name is not None and _CASH_AREA.search(a.area_name)]
    return [a for a in accounts if _CASH.search(a.name) and not _NOT_CASH.search(a.name)]


def bank_cross_check(
    closing: Decimal | None,
    last4: str | None,
    accounts: Sequence[Account] | None,
    has_methodology: bool,
) -> CheckResult:
    """The statement's closing balance against the cash account it's for (SPEC-029 Q5)."""
    if accounts is None:
        return _na("no_trial_balance")
    if closing is None:
        return _na("no_closing_balance")
    cash = cash_accounts(accounts, has_methodology)
    matched = [a for a in cash if last4 is not None and last4 in re.sub(r"\D", "", a.name)]
    if len(matched) == 1:
        return _result(matched[0].code, closing, matched[0].balance)
    if not matched and len(cash) == 1:
        return _result(cash[0].code, closing, cash[0].balance)
    return _na("account_unclear" if cash else "no_cash_account")


def _control(accounts: Sequence[Account], pattern: re.Pattern[str]) -> list[Account]:
    return [a for a in accounts if pattern.search(a.name) and not _ALLOWANCE.search(a.name)]


def aging_cross_check(
    grand_total: Decimal | None,
    payables: bool,
    accounts: Sequence[Account] | None,
) -> CheckResult:
    """The aging's grand total against its control accounts (debit-normal receivables,
    credit-normal payables)."""
    if accounts is None:
        return _na("no_trial_balance")
    if grand_total is None:
        return _na("no_grand_total")
    control = _control(accounts, _PAYABLE if payables else _RECEIVABLE)
    if not control:
        return _na("no_control_account")
    sign: Callable[[Decimal], Decimal] = (lambda b: -b) if payables else (lambda b: b)
    book = sum((sign(a.balance) for a in control), Decimal(0))
    return _result(",".join(a.code for a in control), grand_total, book)
