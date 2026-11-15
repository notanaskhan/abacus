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
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Final, cast

from abacus.modules.connections.fake_format import MAX_LINES, MAX_PAYLOAD_BYTES, MAX_TEXT
from abacus.modules.ledger.api import LedgerLine, NormalisedTrialBalance, NormaliseError

# C-01-T16: Intuit's classifications in the ledger's words (C9 v2.1 `Classification`).
_CLASSIFICATIONS: Final = {
    "Asset": "asset",
    "Liability": "liability",
    "Equity": "equity",
    "Revenue": "income",
    "Expense": "expense",
}
# Subtypes whose balance runs against their classification (shown in parentheses, CLS-04).
_CONTRA_SUBTYPES: Final = frozenset(
    {"AccumulatedDepreciation", "AccumulatedAmortization", "AccumulatedDepletion"}
    | {"AccumulatedAmortizationOfOtherAsset", "DiscountsRefundsGiven"}
)
_ID: Final = re.compile(r"[0-9A-Za-z-]{1,64}")

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


# --- C-01-T16: the chart of accounts and the general-ledger detail (C9 v2.1) -------------------


@dataclass(frozen=True)
class QboAccount:
    """One account of the chart (`ledger_accounts`, C-01-T10): Intuit's id is stable across
    renames, so it is the external id."""

    external_id: str
    number: str | None
    name: str
    classification: str
    account_type: str
    account_subtype: str | None
    parent_external_id: str | None
    is_contra: bool
    active: bool


@dataclass(frozen=True)
class QboRegisterLine:
    """One row of an account's register, with the other side of its transaction (the split
    account) as `offset_account_ref`. Signed in the account's natural direction, as Intuit's
    report prints it."""

    line_ref: str
    account_ref: str
    external_txn_id: str | None
    txn_date: date
    txn_type: str | None
    doc_number: str | None
    payee: str | None
    memo: str | None
    offset_account_ref: str | None
    amount: Decimal


def _load(content: bytes) -> dict[str, object]:
    if len(content) > MAX_PAYLOAD_BYTES:
        raise NormaliseError("payload_too_large")
    try:
        return _object(json.loads(content.decode("utf-8"), object_pairs_hook=_no_duplicates))
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise NormaliseError("malformed_payload") from None


def _optional_text(value: object) -> str | None:
    if value is None or value == "":
        return None
    return _text(value)


def _identifier(value: object) -> str:
    text = _text(value)
    if not _ID.fullmatch(text):
        raise NormaliseError("malformed_payload")
    return text


def parse_qbo_accounts(content: bytes) -> tuple[QboAccount, ...]:
    """A page of `select * from Account` (`QueryResponse.Account[]`)."""
    response = _object(_load(content).get("QueryResponse"))
    raw = response.get("Account", [])
    if not isinstance(raw, list) or len(cast(list[object], raw)) > MAX_LINES:
        raise NormaliseError("malformed_payload")
    out: list[QboAccount] = []
    for item in cast(list[object], raw):
        account = _object(item)
        classification = _CLASSIFICATIONS.get(_text(account.get("Classification")))
        if classification is None:
            raise NormaliseError("malformed_payload")
        subtype = _optional_text(account.get("AccountSubType"))
        parent = account.get("ParentRef")
        active = account.get("Active", True)
        if not isinstance(active, bool):
            raise NormaliseError("malformed_payload")
        out.append(
            QboAccount(
                external_id=_identifier(account.get("Id")),
                number=_optional_text(account.get("AcctNum")),
                name=_text(account.get("Name")),
                classification=classification,
                account_type=_text(account.get("AccountType")),
                account_subtype=subtype,
                parent_external_id=(
                    _identifier(_object(parent).get("value")) if parent is not None else None
                ),
                is_contra=subtype in _CONTRA_SUBTYPES,
                active=active,
            )
        )
    return tuple(out)


_GL_KEYS: Final = (
    "tx_date",
    "txn_type",
    "doc_num",
    "name",
    "memo",
    "split_acc",
    "subt_nat_amount",
)


def _column_keys(document: dict[str, object]) -> list[str]:
    columns = _object(document.get("Columns")).get("Column")
    if not isinstance(columns, list):
        raise NormaliseError("malformed_payload")
    keys: list[str] = []
    for raw in cast(list[object], columns):
        meta = _object(raw).get("MetaData", [])
        key = ""
        for entry in cast(list[object], meta) if isinstance(meta, list) else []:
            item = _object(entry)
            if item.get("Name") == "ColKey":
                key = _text(item.get("Value"))
        keys.append(key)
    if not set(_GL_KEYS) <= set(keys):
        raise NormaliseError("malformed_payload")
    return keys


def parse_qbo_general_ledger(content: bytes) -> tuple[QboRegisterLine, ...]:
    """The GeneralLedger report: one section per account (its header names the account), data
    rows in the register columns. Summary rows are the provider's subtotals and are skipped; the
    close engine foots its own."""
    document = _load(content)
    keys = _column_keys(document)
    out: list[QboRegisterLine] = []

    def walk(rows: object, account: str | None, depth: int) -> None:
        if depth > 8:
            raise NormaliseError("malformed_payload")
        found: object = _object(rows).get("Row", []) if rows is not None else []
        if not isinstance(found, list):
            raise NormaliseError("malformed_payload")
        for raw in cast(list[object], found):
            row = _object(raw)
            if row.get("type") == "Section" or "Header" in row:
                header = row.get("Header")
                cells = _object(header).get("ColData") if header is not None else None
                section_account = account
                if isinstance(cells, list) and cells:
                    first = _object(cast(list[object], cells)[0])
                    if first.get("id"):
                        section_account = _identifier(first.get("id"))
                walk(row.get("Rows"), section_account, depth + 1)
                continue
            if row.get("type") != "Data" or account is None:
                continue
            raw_cells = row.get("ColData")
            if not isinstance(raw_cells, list) or len(cast(list[object], raw_cells)) != len(keys):
                raise NormaliseError("malformed_payload")
            cell = dict(
                zip(keys, (_object(c) for c in cast(list[object], raw_cells)), strict=True)
            )
            if len(out) >= MAX_LINES:
                raise NormaliseError("malformed_payload")
            txn = cell["txn_type"].get("id")
            txn_id = _identifier(txn) if txn else None
            split = cell["split_acc"].get("id")
            index = sum(1 for line in out if line.external_txn_id == txn_id and txn_id)
            out.append(
                QboRegisterLine(
                    line_ref=f"qbo:{account}:{txn_id or 'none'}:{index}",
                    account_ref=account,
                    external_txn_id=txn_id,
                    txn_date=_date(cell["tx_date"].get("value")),
                    txn_type=_optional_text(cell["txn_type"].get("value")),
                    doc_number=_optional_text(cell["doc_num"].get("value")),
                    payee=_optional_text(cell["name"].get("value")),
                    memo=_optional_text(cell["memo"].get("value")),
                    offset_account_ref=_identifier(split) if split else None,
                    amount=_signed(cell["subt_nat_amount"].get("value")),
                )
            )

    walk(document.get("Rows"), None, 0)
    return tuple(out)
