"""Parse a QuickBooks Online TrialBalance report into the common ledger model (A-02-T26; ADR-038,
ADR-050; DEC-709).

The report's JSON (`/v3/company/{realm}/reports/TrialBalance`): `Header` (`StartPeriod`,
`EndPeriod`, `Currency`), `Columns` (Account, Debit, Credit) and `Rows.Row[]`, each a data row
with `ColData` `[account {value, id}, debit, credit]`, plus one `Summary` row (`group` GrandTotal)
whose debit and credit are the provider's control totals. Provider content is hostile
(AGENTS.md #8): the same limits and refusals as the fake format (size cap, strict UTF-8, no
duplicate keys, plain decimal amounts, no control or format characters). A blank amount is zero;
a negative amount on one side (QuickBooks shows contra balances so) moves to the other side, by
code. The account code is the QuickBooks account id, stable across renames; the name is the
row's label.
"""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import date
from decimal import Decimal
from typing import Final, cast

from abacus.modules.connections.fake_format import MAX_LINES, MAX_PAYLOAD_BYTES, MAX_TEXT
from abacus.modules.ledger.api import LedgerLine, NormalisedTrialBalance, NormaliseError

_SIGNED: Final = re.compile(r"-?[0-9]{1,15}(?:\.[0-9]{1,2})?")
_CENT: Final = Decimal("0.01")
_ZERO: Final = Decimal("0.00")
_REFUSED_CATEGORIES: Final = frozenset({"Cc", "Cf", "Cs", "Co", "Zl", "Zp"})


# The fake format's own guards, repeated here: that module is protected and keeps them private.
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


def _date(value: object) -> date:
    try:
        return date.fromisoformat(_text(value))
    except ValueError:
        raise NormaliseError("malformed_payload") from None


def _signed(value: object) -> Decimal:
    if not isinstance(value, str):
        raise NormaliseError("malformed_payload")
    if value == "":
        return _ZERO
    if not _SIGNED.fullmatch(value):
        raise NormaliseError("invalid_amount")
    return Decimal(value).quantize(_CENT)


def _cells(row: dict[str, object], key: str) -> list[dict[str, object]]:
    raw = row.get(key)
    if not isinstance(raw, list) or len(cast(list[object], raw)) != 3:
        raise NormaliseError("malformed_payload")
    return [_object(c) for c in cast(list[object], raw)]


def _sides(debit: Decimal, credit: Decimal) -> tuple[Decimal, Decimal]:
    """A negative on one side is a balance on the other (code, never a model, ADR-050)."""
    if debit < 0:
        credit, debit = credit - debit, _ZERO
    if credit < 0:
        debit, credit = debit - credit, _ZERO
    return debit, credit


def parse_qbo_trial_balance(content: bytes) -> NormalisedTrialBalance:
    if len(content) > MAX_PAYLOAD_BYTES:
        raise NormaliseError("payload_too_large")
    try:
        document = _object(json.loads(content.decode("utf-8"), object_pairs_hook=_no_duplicates))
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise NormaliseError("malformed_payload") from None
    header = _object(document.get("Header"))
    rows = _object(document.get("Rows")).get("Row")
    if not isinstance(rows, list) or len(cast(list[object], rows)) > MAX_LINES:
        raise NormaliseError("malformed_payload")
    lines: list[LedgerLine] = []
    totals: tuple[Decimal, Decimal] | None = None
    for raw in cast(list[object], rows):
        row = _object(raw)
        if "Summary" in row:
            if row.get("group") != "GrandTotal" or totals is not None:
                raise NormaliseError("malformed_payload")
            cells = _cells(_object(row["Summary"]), "ColData")
            totals = (_signed(cells[1].get("value")), _signed(cells[2].get("value")))
            continue
        account, debit, credit = _cells(row, "ColData")
        dr, cr = _sides(_signed(debit.get("value")), _signed(credit.get("value")))
        code = _text(account.get("id"))
        lines.append(
            LedgerLine(
                account_code=code,
                account_name=_text(account.get("value")),
                debit=dr,
                credit=cr,
                source_ref=f"qbo:account:{code}",
            )
        )
    if totals is None:
        raise NormaliseError("malformed_payload")
    return NormalisedTrialBalance(
        period_start=_date(header.get("StartPeriod")),
        period_end=_date(header.get("EndPeriod")),
        currency=_text(header.get("Currency")),
        lines=tuple(lines),
        declared_debit=totals[0],
        declared_credit=totals[1],
    )
