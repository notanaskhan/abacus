"""General ledger detail: the common model and its completeness checks (SPEC-034; TASK-069;
ADR-038, ADR-050). PROTECTED.

A parser (connections) reads an export into `GlEntry` lines and a `GlSummary`: per account its
opening balance (when the export prints one), debits and credits, plus the months the lines fall
in. `validate_gl` proves by code that the detail is complete against the year-end trial balance,
in a fixed order: period coverage, balance, missing and extra accounts, then each account's roll
forward (opening + debits - credits = trial balance closing, to the cent). Nothing is judged by a
model; every amount in a failure's details is computed here.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Final, Protocol

MAX_DETAILS: Final = 5
# Balance sheet accounts by the common US numbering (assets, liabilities, equity), used only when
# an export prints no opening balances at all (SPEC-034 Q6).
_BALANCE_SHEET_DIGITS: Final = frozenset("123")


@dataclass(frozen=True)
class GlEntry:
    line_no: int
    account_code: str
    account_name: str
    posted_on: date
    reference: str | None
    kind: str | None  # the transaction type ("Invoice", "Payment", "Journal")
    counterparty: str | None
    description: str | None
    debit: Decimal
    credit: Decimal
    source_ref: str


@dataclass(frozen=True)
class GlAccount:
    code: str
    name: str
    opening: Decimal | None  # as printed (debit positive); None when the export printed none
    debit: Decimal
    credit: Decimal


@dataclass(frozen=True)
class GlSummary:
    line_count: int
    total_debit: Decimal
    total_credit: Decimal
    accounts: tuple[GlAccount, ...]
    months: frozenset[tuple[int, int]]  # (year, month) with at least one line
    outside_period: int  # lines dated outside the fiscal year
    has_openings: bool  # the export printed opening balances


@dataclass(frozen=True)
class TbAccount:
    code: str
    name: str
    closing: Decimal  # debit minus credit at the year end


@dataclass(frozen=True)
class Balance:
    code: str
    name: str
    opening: Decimal
    debit: Decimal
    credit: Decimal
    closing: Decimal
    tb_closing: Decimal
    opening_derived: bool


@dataclass(frozen=True)
class GlCheck:
    failure: str | None
    accounts: tuple[tuple[str, Decimal], ...] = ()  # (code, difference), at most five
    months: tuple[str, ...] = ()  # missing months as YYYY-MM
    balances: tuple[Balance, ...] = field(default=())


def identity(code: str) -> str:
    """Codes that render alike are the same account (as for trial balances)."""
    return unicodedata.normalize("NFKC", code).casefold()


def _months(start: date, end: date) -> list[tuple[int, int]]:
    found: list[tuple[int, int]] = []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        found.append((year, month))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return found


def _balance_sheet(account_code: str, opening: Decimal | None, has_openings: bool) -> bool:
    """With openings printed, an account with one is a balance sheet account; without any, by
    its number."""
    if has_openings:
        return opening is not None
    return account_code[:1] in _BALANCE_SHEET_DIGITS


def validate_gl(
    gl: GlSummary, tb: Sequence[TbAccount], *, period_start: date, period_end: date
) -> GlCheck:
    """None as `failure` if the detail is complete; otherwise the first failing check's code and
    its details. `balances` is the reconciliation, every account, either way."""
    by_code = {identity(a.code): a for a in tb}
    detail = {identity(a.code): a for a in gl.accounts}
    balances: list[Balance] = []
    for key in sorted(set(by_code) | set(detail)):
        account = detail.get(key)
        tb_account = by_code.get(key)
        tb_closing = tb_account.closing if tb_account is not None else Decimal(0)
        debit = account.debit if account is not None else Decimal(0)
        credit = account.credit if account is not None else Decimal(0)
        printed = account.opening if account is not None else None
        if account is not None:
            code, name = account.code, account.name
        elif tb_account is not None:
            code, name = tb_account.code, tb_account.name
        else:  # pragma: no cover - every key comes from one side or the other
            continue
        if printed is not None:
            opening, derived = printed, False
        elif not gl.has_openings and _balance_sheet(code, None, False):
            opening, derived = tb_closing - (debit - credit), True  # Q6: derived, and flagged
        else:
            opening, derived = Decimal(0), False
        balances.append(
            Balance(
                code, name, opening, debit, credit, opening + debit - credit, tb_closing, derived
            )
        )
    result = tuple(balances)

    def printed_opening(code: str) -> Decimal | None:
        found = detail.get(identity(code))
        return found.opening if found is not None else None

    income_activity = any(
        a.closing != 0 and not _balance_sheet(a.code, printed_opening(a.code), gl.has_openings)
        for a in tb
    )
    missing_months = (
        [m for m in _months(period_start, period_end) if m not in gl.months]
        if income_activity
        else []
    )
    if gl.outside_period or missing_months:
        return GlCheck(
            "period_mismatch",
            months=tuple(f"{y:04d}-{m:02d}" for y, m in missing_months[:12]),
            balances=result,
        )
    if gl.total_debit != gl.total_credit:
        return GlCheck("unbalanced", (("", gl.total_debit - gl.total_credit),), balances=result)
    missing = [b for b in result if b.tb_closing != 0 and identity(b.code) not in detail]
    if missing:
        return GlCheck(
            "missing_account",
            tuple((b.code, b.tb_closing) for b in missing[:MAX_DETAILS]),
            balances=result,
        )
    extra = [b for b in result if identity(b.code) not in by_code and b.closing != 0]
    if extra:
        return GlCheck(
            "extra_account",
            tuple((b.code, b.closing) for b in extra[:MAX_DETAILS]),
            balances=result,
        )
    drift = [b for b in result if b.closing != b.tb_closing]
    if drift:
        return GlCheck(
            "roll_forward",
            tuple((b.code, b.closing - b.tb_closing) for b in drift[:MAX_DETAILS]),
            balances=result,
        )
    return GlCheck(None, balances=result)


# --- Journal entries (TASK-070 D2; moved here by TASK-083 D1) ------------------------------------


class Posting(Protocol):
    """What grouping needs from a posting (a `GlEntry`, or evidence's rendering row)."""

    @property
    def line_no(self) -> int: ...
    @property
    def posted_on(self) -> date: ...
    @property
    def kind(self) -> str | None: ...
    @property
    def reference(self) -> str | None: ...
    @property
    def counterparty(self) -> str | None: ...


JournalKey = tuple[str, str, str, str]


def journal_key(e: Posting) -> JournalKey:
    """A transaction is its date, type and reference; without a reference, its date, type and
    name. The journal listing and journal entry testing both group by this, so "an entry" means
    one thing everywhere."""
    reference = e.reference or ""
    return (
        e.posted_on.isoformat(),
        e.kind or "",
        reference,
        "" if reference else (e.counterparty or ""),
    )


def journals[P: Posting](entries: Iterable[P]) -> Iterator[tuple[JournalKey, list[P]]]:
    """The postings grouped by transaction, in date, type, reference order (lines by line no)."""
    grouped: dict[JournalKey, list[P]] = {}
    for e in entries:
        grouped.setdefault(journal_key(e), []).append(e)
    for key in sorted(grouped):
        yield key, sorted(grouped[key], key=lambda x: x.line_no)
