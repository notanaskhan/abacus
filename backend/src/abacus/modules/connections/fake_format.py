"""Parse the fake provider's trial balance JSON into the common ledger model (ADR-038, ADR-050).
PROTECTED. TASK-010 design §5 stage 3, revision 1.

Provider content is hostile (AGENTS.md #8). Before parsing: a size cap, strict UTF-8, no
duplicate keys (raw bytes and parsed data can't disagree). Amounts must be plain decimal strings
(up to 15 digits, up to 2 decimals): no exponents, signs, underscores, spaces or non-ASCII
digits. Text is refused if it contains control, format, surrogate, private-use or line or
paragraph separator characters. Anything unexpected is a `NormaliseError` with a short code.
"""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import date
from decimal import Decimal
from typing import cast

from abacus.modules.ledger.api import LedgerLine, NormalisedTrialBalance, NormaliseError

MAX_PAYLOAD_BYTES = 20 * 1024 * 1024
MAX_LINES = 50_000
MAX_TEXT = 200
_AMOUNT = re.compile(r"[0-9]{1,15}(?:\.[0-9]{1,2})?")
_CENT = Decimal("0.01")
_REFUSED_CATEGORIES = frozenset({"Cc", "Cf", "Cs", "Co", "Zl", "Zp"})


def _no_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    keys = [key for key, _ in pairs]
    if len(set(keys)) != len(keys):
        raise NormaliseError("malformed_payload")
    return dict(pairs)


def _object(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise NormaliseError("malformed_payload")
    return cast(dict[str, object], value)


def _text(value: object) -> str:
    if not isinstance(value, str):
        raise NormaliseError("malformed_payload")
    text = value.strip()
    if not text or len(text) > MAX_TEXT:
        raise NormaliseError("malformed_payload")
    if any(unicodedata.category(c) in _REFUSED_CATEGORIES for c in text):
        raise NormaliseError("malformed_payload")
    return text


def _amount(value: object) -> Decimal:
    if not isinstance(value, str):
        raise NormaliseError("malformed_payload")  # JSON numbers would be floats
    if not _AMOUNT.fullmatch(value):
        raise NormaliseError("invalid_amount")
    return Decimal(value).quantize(_CENT)


def _date(value: object) -> date:
    try:
        return date.fromisoformat(_text(value))
    except ValueError:
        raise NormaliseError("malformed_payload") from None


def parse_trial_balance(content: bytes) -> NormalisedTrialBalance:
    if len(content) > MAX_PAYLOAD_BYTES:
        raise NormaliseError("payload_too_large")
    try:
        text = content.decode("utf-8")
        document = _object(json.loads(text, object_pairs_hook=_no_duplicates))
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise NormaliseError("malformed_payload") from None
    if document.get("dataset") != "trial_balance":
        raise NormaliseError("malformed_payload")
    period = _object(document.get("period"))
    raw_lines = document.get("lines")
    if not isinstance(raw_lines, list) or len(cast(list[object], raw_lines)) > MAX_LINES:
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
        currency=_text(document.get("currency")),
        lines=tuple(lines),
        declared_debit=_amount(totals.get("debit")),
        declared_credit=_amount(totals.get("credit")),
    )
