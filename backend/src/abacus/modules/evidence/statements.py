"""Reading a statement's transactions (SPEC-312 phase 2; TASK-324; ADR-050, ADR-052).

Pure code over a statement's text (a PDF's pages), a CSV export or an OFX file. Every amount is
an exact `Decimal` in one convention: its effect on the statement balance (a card charge or a
bank deposit is positive; a card payment or a bank withdrawal is negative). Code reconciles:
opening balance plus the lines must equal the closing balance, or the statement can't be
approved. Nothing here guesses a balance the document doesn't print; a person enters it.

The text is hostile (ADR-052): every string is capped and stripped of control characters, and
the caller runs this in the isolated child.
"""

from __future__ import annotations

import csv
import io
import re
import unicodedata
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Final, Literal

Format = Literal["pdf_text", "csv", "ofx"]
AccountKind = Literal["credit_card", "bank", "unknown"]
MAX_LINES: Final = 5000
MAX_DESCRIPTION: Final = 200
_REFUSED: Final = frozenset({"Cc", "Cf", "Cs", "Co"})
_CENTS: Final = Decimal("0.01")

_DATE: Final = r"\d{1,2}/\d{1,2}(?:/\d{2,4})?"
_MONTH: Final = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}"
_AMOUNT: Final = r"[-+]?\s?\(?\$?\s?[-+]?[\d,]*\d\.\d{2}\)?"
_LINE: Final = re.compile(
    rf"^\s*(?P<d1>{_DATE}|{_MONTH})\s+(?:(?P<d2>{_DATE}|{_MONTH})\s+)?(?P<desc>.+?)\s+"
    rf"(?P<amt>{_AMOUNT})\s*(?P<cr>CR)?\s*$",
    re.IGNORECASE,
)
_MONTHS: Final = {
    m: i
    for i, m in enumerate(
        ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1
    )
}
_CARD: Final = re.compile(
    r"credit card|card ending|card member|cardmember|minimum payment|payment due date", re.I
)
_LAST4: Final = re.compile(
    r"(?:card|account)\s+(?:ending|number)(?:\s+in)?[:\s#]*[xX*•\-\s]*(\d{4})\b"
    r"|(?:[xX*•]{4}[\s-]?){1,3}(\d{4})\b",
    re.I,
)
_PERIOD: Final = re.compile(
    rf"(?:opening\s*/\s*closing\s+date|statement\s+period|billing\s+period|"
    rf"for\s+the\s+period)[:\s]*(?P<a>{_DATE})\s*(?:-|to|through)\s*(?P<b>{_DATE})",
    re.I,
)
_SUMMARY: Final = {
    "opening": re.compile(
        rf"(?:previous|beginning|opening)\s+balance\s*[:]?\s*(?P<v>{_AMOUNT})", re.I
    ),
    "closing": re.compile(
        rf"(?:new|ending|closing|statement)\s+balance\s*[:]?\s*(?P<v>{_AMOUNT})", re.I
    ),
}
_CREDIT_HEADINGS: Final = re.compile(
    r"^\s*(payments?(?:,| and)\s*(?:other\s+)?credits|credits|returns|"
    r"withdrawals|checks|electronic (?:payments|withdrawals)|debits)\b",
    re.I,
)
_CHARGE_HEADINGS: Final = re.compile(
    r"^\s*(purchases|transactions|fees(?: charged)?|interest(?: charged)?|cash advances|"
    r"deposits(?: and (?:other )?(?:additions|credits))?)\b",
    re.I,
)
_HAS_AMOUNT: Final = re.compile(r"\d\.\d{2}\b")
_CREDIT_WORDS: Final = re.compile(r"\b(payment|thank you|refund|return|credit|reversal)\b", re.I)


@dataclass(frozen=True)
class StatementLine:
    position: int
    posted_on: date | None
    description: str
    amount: Decimal  # effect on the statement balance
    page: int | None


@dataclass(frozen=True)
class ParsedStatement:
    format: Format
    account_kind: AccountKind
    issuer: str | None
    last4: str | None
    period_start: date | None
    period_end: date | None
    opening: Decimal | None
    closing: Decimal | None
    lines: tuple[StatementLine, ...]
    signs_inferred: bool  # a single amount column whose sign convention code had to infer
    truncated: bool


@dataclass(frozen=True)
class Reconciliation:
    opening: Decimal | None
    lines_total: Decimal
    expected_closing: Decimal | None
    closing: Decimal | None
    difference: Decimal | None  # closing minus (opening + lines); None without both balances
    reconciled: bool


def clean(text: str, limit: int = MAX_DESCRIPTION) -> str:
    kept = "".join(c for c in text if unicodedata.category(c) not in _REFUSED)
    return " ".join(kept.split())[:limit]


def amount_of(text: str) -> Decimal | None:
    raw = text.replace("$", "").replace(",", "").replace(" ", "")
    negative = raw.startswith("-") or (raw.startswith("(") and raw.endswith(")"))
    raw = raw.strip("()+-")
    try:
        value = Decimal(raw).quantize(_CENTS)
    except InvalidOperation:
        return None
    return -value if negative else value


def date_of(text: str, period_end: date | None) -> date | None:
    """`12/09`, `12/09/26`, `12/09/2026` or `Dec 9`; a date without a year takes the statement
    year, or the year before for a month after the period end (a December line on a January
    statement)."""
    text = text.strip().rstrip(".")
    month = day = None
    year: int | None = None
    if "/" in text:
        parts = [int(p) for p in text.split("/")]
        month, day = parts[0], parts[1]
        if len(parts) == 3:
            year = parts[2] + (2000 if parts[2] < 100 else 0)
    else:
        name, _, number = text.partition(" ")
        month = _MONTHS.get(name[:3].lower())
        day = int(number.strip()) if number.strip().isdigit() else None
    if month is None or day is None:
        return None
    if year is None:
        if period_end is None:
            return None
        year = period_end.year - (1 if month > period_end.month else 0)
    try:
        return date(year, month, day)
    except ValueError:
        return None


def reconcile(
    opening: Decimal | None,
    lines: tuple[StatementLine, ...] | list[StatementLine],
    closing: Decimal | None,
) -> Reconciliation:
    total = sum((line.amount for line in lines), Decimal("0.00"))
    if opening is None or closing is None:
        return Reconciliation(opening, total, None, closing, None, False)
    expected = opening + total
    return Reconciliation(
        opening, total, expected, closing, closing - expected, closing == expected
    )


# --- PDF text ---------------------------------------------------------------------------------


def from_pages(pages: tuple[str, ...] | list[str]) -> ParsedStatement:
    text = "\n".join(pages)
    kind: AccountKind = (
        "credit_card"
        if _CARD.search(text)
        else ("bank" if re.search(r"\b(checking|savings|deposits?)\b", text, re.I) else "unknown")
    )
    period = _PERIOD.search(text)
    end = date_of(period.group("b"), None) if period else None
    start = date_of(period.group("a"), end) if period else None
    found: dict[str, Decimal | None] = {}
    for key, pattern in _SUMMARY.items():
        m = pattern.search(text)
        found[key] = amount_of(m.group("v")) if m else None
    last4 = next((g for m in _LAST4.finditer(text) for g in m.groups() if g), None)
    issuer = clean(next((ln for ln in text.splitlines() if ln.strip()), ""), 80) or None
    lines: list[StatementLine] = []
    truncated = False
    for number, page in enumerate(pages, start=1):
        section: Literal["credit", "charge"] | None = None
        for raw in page.splitlines():
            heading = not _HAS_AMOUNT.search(
                raw
            )  # a summary line carries its total; a heading doesn't
            if heading and _CREDIT_HEADINGS.match(raw):
                section = "credit"
                continue
            if heading and _CHARGE_HEADINGS.match(raw):
                section = "charge"
                continue
            m = _LINE.match(raw)
            if m is None:
                continue
            value = amount_of(m.group("amt"))
            if value is None:
                continue
            description = clean(m.group("desc"))
            printed_negative = value < 0 or bool(m.group("cr"))
            magnitude = abs(value)
            if printed_negative or section == "credit":
                signed = -magnitude
            elif section == "charge":
                signed = magnitude
            else:  # no heading and no sign: words decide, a charge otherwise
                signed = -magnitude if _CREDIT_WORDS.search(description) else magnitude
            if len(lines) >= MAX_LINES:
                truncated = True
                break
            posted = date_of(m.group("d2") or m.group("d1"), end)
            lines.append(StatementLine(len(lines) + 1, posted, description, signed, number))
    return ParsedStatement(
        "pdf_text",
        kind,
        issuer,
        last4,
        start,
        end,
        found["opening"],
        found["closing"],
        tuple(lines),
        False,
        truncated,
    )


# --- CSV --------------------------------------------------------------------------------------

_DATE_COLS: Final = (
    "transaction date",
    "trans date",
    "trans. date",
    "date",
    "posted date",
    "post date",
    "posting date",
)
_DESC_COLS: Final = ("description", "merchant", "payee", "name", "details", "memo")
_AMOUNT_COLS: Final = ("amount", "transaction amount")
_DEBIT_COLS: Final = ("debit", "charges", "charge", "withdrawal", "withdrawals")
_CREDIT_COLS: Final = ("credit", "payments", "payment", "deposit", "deposits")


def _col(header: list[str], names: tuple[str, ...]) -> int | None:
    lowered = [h.strip().lower() for h in header]
    for name in names:
        if name in lowered:
            return lowered.index(name)
    return None


def _cell(row: list[str], index: int | None) -> str:
    return row[index] if index is not None and index < len(row) else ""


def _csv_date(text: str) -> date | None:
    text = text.strip()
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", text)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    return date_of(text, None) if text.count("/") == 2 else None


def from_csv(text: str) -> ParsedStatement | None:
    rows = list(csv.reader(io.StringIO(text)))
    for index, header in enumerate(rows[:10]):
        d = _col(header, _DATE_COLS)
        desc = _col(header, _DESC_COLS)
        amount = _col(header, _AMOUNT_COLS)
        debit, credit = _col(header, _DEBIT_COLS), _col(header, _CREDIT_COLS)
        if d is None or desc is None or (amount is None and debit is None and credit is None):
            continue
        lines: list[StatementLine] = []
        for row in rows[index + 1 :]:
            if len(lines) >= MAX_LINES:
                break
            posted = _csv_date(_cell(row, d))
            if posted is None:
                continue
            if amount is not None:
                value = amount_of(_cell(row, amount))
            else:
                dv, cv = amount_of(_cell(row, debit) or "0"), amount_of(_cell(row, credit) or "0")
                value = None if dv is None or cv is None else dv - cv
            if value is None:
                continue
            lines.append(
                StatementLine(len(lines) + 1, posted, clean(_cell(row, desc)), value, None)
            )
        if not lines:
            return None
        dates = [line.posted_on for line in lines if line.posted_on is not None]
        single = amount is not None
        if single and sum(1 for line in lines if line.amount < 0) > len(lines) / 2:
            # Most rows negative: the export prints charges as negatives (as several issuers
            # do); turn them into effects on the balance. The reviewer can flip it back.
            lines = [replace(line, amount=-line.amount) for line in lines]
        return ParsedStatement(
            "csv",
            "unknown",
            None,
            None,
            min(dates),
            max(dates),
            None,
            None,
            tuple(lines),
            single,
            len(rows) - index - 1 > MAX_LINES,
        )
    return None


# --- OFX --------------------------------------------------------------------------------------

_OFX_TXN: Final = re.compile(
    r"<STMTTRN>(.*?)(?:</STMTTRN>|(?=<STMTTRN>)|(?=</BANKTRANLIST>))", re.I | re.S
)


def _tag(block: str, name: str) -> str | None:
    m = re.search(rf"<{name}>([^<\r\n]*)", block, re.I)
    return m.group(1).strip() if m else None


def _ofx_date(text: str | None) -> date | None:
    if text is None or len(text) < 8 or not text[:8].isdigit():
        return None
    try:
        return date(int(text[:4]), int(text[4:6]), int(text[6:8]))
    except ValueError:
        return None


def from_ofx(text: str) -> ParsedStatement | None:
    if "<OFX>" not in text.upper():
        return None
    card = "<CCSTMTRS>" in text.upper()
    # OFX amounts are the account holder's view: for a card a charge is negative, so its effect
    # on the balance owed is the opposite; for a bank account they already are the effect.
    flip = Decimal(-1) if card else Decimal(1)
    lines: list[StatementLine] = []
    for m in _OFX_TXN.finditer(text):
        block = m.group(1)
        value = amount_of(_tag(block, "TRNAMT") or "")
        if value is None:
            continue
        description = " ".join(p for p in (_tag(block, "NAME"), _tag(block, "MEMO")) if p)
        lines.append(
            StatementLine(
                len(lines) + 1,
                _ofx_date(_tag(block, "DTPOSTED")),
                clean(description),
                value * flip,
                None,
            )
        )
        if len(lines) >= MAX_LINES:
            break
    ledger = re.search(r"<LEDGERBAL>(.*?)(?:</LEDGERBAL>|$)", text, re.I | re.S)
    closing = amount_of(_tag(ledger.group(1), "BALAMT") or "") if ledger else None
    acct = _tag(text, "ACCTID") or ""
    return ParsedStatement(
        "ofx",
        "credit_card" if card else "bank",
        clean(_tag(text, "ORG") or "", 80) or None,
        acct[-4:] if len(acct) >= 4 and acct[-4:].isdigit() else None,
        _ofx_date(_tag(text, "DTSTART")),
        _ofx_date(_tag(text, "DTEND")),
        None,
        None if closing is None else closing * flip,
        tuple(lines),
        False,
        False,
    )


def from_text_file(content: bytes) -> ParsedStatement | None:
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            text = content.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        return None
    return from_ofx(text) or from_csv(text)
