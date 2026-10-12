"""Fields read from a document's extracted text and tables (SPEC-029 goal 3; TASK-054). PROTECTED.

Pure functions, run inside the isolated child with the rest of extraction. Code reads; nothing
here judges a document (ADR-050). The labels are the general ones US bank statements and aging
reports print ("Statement period", "Ending balance", "Current", "1-30", "Total"), checked against
synthetic documents in several layouts; anything not found is None, never guessed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Final

_MONTHS: Final = (
    "January|February|March|April|May|June|July|August|September|October|November|December|"
    "Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec"
)
DATE: Final = (
    rf"(?:(?:{_MONTHS})\.? \d{{1,2}}, \d{{4}}|\d{{1,2}} (?:{_MONTHS}) \d{{4}}"
    r"|\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2})"
)
AMOUNT: Final = r"\(?-?\$?\s?-?[0-9][0-9,]*\.[0-9]{2}\)?"
_DATE_FORMATS: Final = (
    "%B %d, %Y",
    "%b %d, %Y",
    "%d %B %Y",
    "%d %b %Y",
    "%m/%d/%Y",
    "%Y-%m-%d",
)
_DATE_RE: Final = re.compile(DATE)
_AMOUNT_RE: Final = re.compile(AMOUNT)
_HOLDER: Final = re.compile(
    r"(?:Account (?:holder|name)|Statement for|Prepared for)\s*:?\s*(?P<v>[^\n]{2,120})", re.I
)
_LAST4: Final = re.compile(
    r"Account (?:number|no\.?|#)\s*:?\s*[*xX•\-\s0-9]*?(?P<v>[0-9]{4})\b(?![0-9])", re.I
)
_PERIOD: Final = re.compile(
    rf"(?:Statement period|For the period|Period)\s*:?\s*(?:from\s+)?(?P<a>{DATE})\s*"
    rf"(?:to|through|thru|-|\u2013)\s*(?P<b>{DATE})",
    re.I,
)
_STATEMENT_DATE: Final = re.compile(rf"(?:Statement date|Closing date)\s*:?\s*(?P<b>{DATE})", re.I)
_OPENING: Final = re.compile(
    rf"(?:Beginning|Opening|Previous) balance[^\n0-9$(\-]*?(?P<v>{AMOUNT})", re.I
)
_CLOSING: Final = re.compile(rf"(?:Ending|Closing|New) balance[^\n0-9$(\-]*?(?P<v>{AMOUNT})", re.I)
_CREDITS: Final = re.compile(
    r"(?:Total deposits(?: and (?:other )?credits)?|Deposits and (?:other )?credits"
    r"|Total credits)"
    rf"[^\n0-9$(\-]*?(?P<v>{AMOUNT})",
    re.I,
)
_DEBITS: Final = re.compile(
    rf"(?:Total withdrawals(?: and (?:other )?debits)?|Withdrawals and (?:other )?debits"
    rf"|Checks and (?:other )?debits|Total debits)[^\n0-9$(\-]*?(?P<v>{AMOUNT})",
    re.I,
)
_AS_OF: Final = re.compile(rf"(?:as of|as at)\s*:?\s*(?P<v>{DATE})", re.I)
_BUCKET: Final = re.compile(
    r"^(?:current|not yet due|\d{1,3}\s*[-\u2013]\s*\d{1,3}(?: days)?|over \d{1,3}(?: days)?"
    r"|\d{1,3}\+(?: days)?|> ?\d{1,3}(?: days)?)$",
    re.I,
)
MAX_FOUND: Final = 200


@dataclass(frozen=True)
class Statement:
    holder: str | None
    account_last4: str | None
    period_start: date | None
    period_end: date | None
    opening: Decimal | None
    closing: Decimal | None
    credits: Decimal | None
    debits: Decimal | None


@dataclass(frozen=True)
class AgingRow:
    """None where a cell has no value code can read (a formula saved without its result)."""

    name: str
    buckets: tuple[Decimal | None, ...]
    total: Decimal | None


@dataclass(frozen=True)
class Aging:
    as_of: date | None
    buckets: tuple[str, ...]
    rows: tuple[AgingRow, ...]
    grand_total: tuple[Decimal | None, ...] | None  # the total row's buckets, then its total


def parse_date(text: str) -> date | None:
    cleaned = re.sub(r"\s+", " ", text.replace(".", "")).strip()
    for pattern in _DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, pattern).date()
        except ValueError:
            continue
    return None


def parse_amount(text: object) -> Decimal | None:
    """`(1,234.56)`, `-1,234.56`, `$1,234.56`; None for anything else (never guessed)."""
    if isinstance(text, bool) or text is None:
        return None
    if isinstance(text, (int, float, Decimal)):
        try:
            return Decimal(str(text)).quantize(Decimal("0.01"))
        except InvalidOperation:
            return None
    raw = str(text).strip().replace("$", "").replace(",", "").replace(" ", "")
    negative = raw.startswith("(") and raw.endswith(")")
    raw = raw.strip("()")
    if not re.fullmatch(r"-?[0-9]{1,15}(?:\.[0-9]{1,2})?", raw):
        return None
    value = Decimal(raw).quantize(Decimal("0.01"))
    return -value if negative else value


def dates_in(text: str) -> tuple[date, ...]:
    found: list[date] = []
    for match in _DATE_RE.finditer(text):
        parsed = parse_date(match.group(0))
        if parsed is not None and parsed not in found:
            found.append(parsed)
        if len(found) >= MAX_FOUND:
            break
    return tuple(found)


def amounts_in(text: str) -> tuple[Decimal, ...]:
    found: list[Decimal] = []
    for match in _AMOUNT_RE.finditer(text):
        parsed = parse_amount(match.group(0))
        if parsed is not None:
            found.append(parsed)
        if len(found) >= MAX_FOUND:
            break
    return tuple(found)


def _first(pattern: re.Pattern[str], text: str, group: str = "v") -> str | None:
    match = pattern.search(text)
    return match.group(group).strip() if match is not None else None


def _amount(pattern: re.Pattern[str], text: str) -> Decimal | None:
    found = _first(pattern, text)
    return parse_amount(found) if found is not None else None


def statement_fields(text: str) -> Statement | None:
    """A bank statement's fields, when the text prints any of them; else None."""
    period = _PERIOD.search(text)
    start = parse_date(period.group("a")) if period is not None else None
    end = parse_date(period.group("b")) if period is not None else None
    if end is None:
        found = _first(_STATEMENT_DATE, text, "b")
        end = parse_date(found) if found is not None else None
    holder = _first(_HOLDER, text)
    found = Statement(
        holder=holder.split("  ")[0].strip() if holder is not None else None,
        account_last4=_first(_LAST4, text),
        period_start=start,
        period_end=end,
        opening=_amount(_OPENING, text),
        closing=_amount(_CLOSING, text),
        credits=_amount(_CREDITS, text),
        debits=_amount(_DEBITS, text),
    )
    if found.closing is None and found.period_end is None:
        return None  # not a statement as far as code can tell
    return found


def _cell(value: object) -> str:
    return "" if value is None else str(value).strip()


def aging_fields(rows: list[list[object]]) -> Aging | None:
    """An aging schedule's buckets, rows and total row, when a header row names at least three
    buckets and a Total column; else None."""
    for n, row in enumerate(rows[:50]):
        labels = [_cell(c) for c in row]
        buckets = [i for i, label in enumerate(labels) if _BUCKET.match(label)]
        total = next((i for i, label in enumerate(labels) if label.casefold() == "total"), None)
        if len(buckets) < 3 or total is None:
            continue
        as_of: date | None = None
        for above in rows[:n]:
            for cell in above:
                found = _first(_AS_OF, _cell(cell))
                as_of = as_of or (parse_date(found) if found is not None else None)
        lines: list[AgingRow] = []
        grand: tuple[Decimal | None, ...] | None = None
        for later in rows[n + 1 :]:
            cells = [*later, *([None] * (len(labels) - len(later)))]
            name = _cell(cells[0])
            values = [parse_amount(cells[i]) for i in buckets]
            row_total = parse_amount(cells[total])
            if not name:
                continue  # a spacer, or a sub-total without a label
            if name.casefold().startswith("total"):
                grand = (*values, row_total)
                break
            if row_total is None and all(v is None for v in values):
                continue  # a heading or a note
            lines.append(AgingRow(name[:200], tuple(values), row_total))
        return Aging(as_of, tuple(labels[i] for i in buckets), tuple(lines), grand)
    return None
