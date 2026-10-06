"""Normalise and validate a provider trial balance (ADR-038, ADR-050). PROTECTED.
TASK-010 design §5, stages 3 and 4.

Provider content is hostile (AGENTS.md #8): parsing is strict, amounts are decimal strings parsed
exactly (never floats), and anything unexpected is a typed failure with a short code. Code
computes totals and checks them; nothing here is judged by a model.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import cast

_CENT = Decimal("0.01")
_MAX_AMOUNT = Decimal("1e15")  # numeric(20, 2) holds 18 digits before the point; far beyond any TB
_MAX_LINES = 50_000
_MAX_TEXT = 200


class NormaliseError(Exception):
    """The payload isn't a well-formed trial balance; `code` is recorded on the sync run."""

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
    lines: tuple[LedgerLine, ...]
    declared_debit: Decimal
    declared_credit: Decimal

    @property
    def total_debit(self) -> Decimal:
        return sum((line.debit for line in self.lines), Decimal(0))

    @property
    def total_credit(self) -> Decimal:
        return sum((line.credit for line in self.lines), Decimal(0))


def _object(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise NormaliseError("malformed_payload")
    return cast(dict[str, object], value)


def _text(value: object) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > _MAX_TEXT:
        raise NormaliseError("malformed_payload")
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise NormaliseError("malformed_payload")
    return value.strip()


def _amount(value: object) -> Decimal:
    if not isinstance(value, str):
        raise NormaliseError("malformed_payload")  # numbers as JSON floats would lose precision
    try:
        amount = Decimal(value)
    except InvalidOperation:
        raise NormaliseError("invalid_amount") from None
    if not amount.is_finite() or amount < 0 or amount >= _MAX_AMOUNT:
        raise NormaliseError("invalid_amount")
    if amount != amount.quantize(_CENT):
        raise NormaliseError("invalid_amount")
    return amount.quantize(_CENT)


def _date(value: object) -> date:
    try:
        return date.fromisoformat(_text(value))
    except ValueError:
        raise NormaliseError("malformed_payload") from None


def normalise(content: bytes) -> NormalisedTrialBalance:
    """Parse the fake provider's trial balance JSON into the common model."""
    try:
        document = _object(json.loads(content))
    except (ValueError, UnicodeDecodeError, RecursionError):
        raise NormaliseError("malformed_payload") from None
    if document.get("dataset") != "trial_balance":
        raise NormaliseError("malformed_payload")
    period = _object(document.get("period"))
    raw_lines = document.get("lines")
    if not isinstance(raw_lines, list) or len(cast(list[object], raw_lines)) > _MAX_LINES:
        raise NormaliseError("malformed_payload")
    lines: list[LedgerLine] = []
    for raw in cast(list[object], raw_lines):
        line = _object(raw)
        lines.append(
            LedgerLine(
                account_code=_text(line.get("code")),
                account_name=_text(line.get("name")),
                debit=_amount(line.get("debit")),
                credit=_amount(line.get("credit")),
                source_ref=_text(line.get("id")),
            )
        )
    totals = _object(document.get("control_totals"))
    return NormalisedTrialBalance(
        period_start=_date(period.get("start")),
        period_end=_date(period.get("end")),
        lines=tuple(lines),
        declared_debit=_amount(totals.get("debit")),
        declared_credit=_amount(totals.get("credit")),
    )


def validate(tb: NormalisedTrialBalance, *, period_start: date, period_end: date) -> str | None:
    """None if the trial balance may be used; otherwise the failure code (ADR-038). Checks in a
    fixed order so the code is stable for the same input."""
    if not tb.lines:
        return "empty"
    if (tb.period_start, tb.period_end) != (period_start, period_end):
        return "period_mismatch"
    codes = [line.account_code for line in tb.lines]
    if len(set(codes)) != len(codes):
        return "duplicate_account"
    if (tb.total_debit, tb.total_credit) != (tb.declared_debit, tb.declared_credit):
        return "control_totals_mismatch"
    if tb.total_debit != tb.total_credit:
        return "unbalanced"
    return None
