"""The bank reconciliation engine (C-01-T22; C-01 §3 F7, §7 R2; CLS-05; ADR-050).

Pure: Decimal only, no clock, no database, no I/O. Code computes both sides of a bank
reconciliation; nothing here asks a model for a figure.

- **Statement lines** come from P-11's `extracted_tables` (one row per transaction, every cell with
  its box): `statement_lines_from_table` reads a table's cells into `StatementLine`s, keeping the
  row's box and the lowest cell confidence. A line below the confidence floor is never matched
  automatically: it is listed in `needs_review` and a person matches it.
- **Matching** pairs a statement line with one register line, first by `reference` (the check
  number and the amount), then by `amount_date` (the same amount and direction within the date
  window, nearest date first). One line matches at most once on each side.
- **Reconciling items.** An unmatched register deposit is a deposit in transit and an unmatched
  register payment an outstanding check (bank side); an unmatched statement deposit is an
  unrecorded deposit and an unmatched statement withdrawal an unrecorded withdrawal (book side).
  Amounts are positive; the kind gives the sign.
- **Carry-forward.** The prior period's open bank-side items are matched against this period's
  statement first; what still has not cleared carries forward with `carried_from` set. A prior
  book-side item clears once a register line in this period records it (`recorded_prior`).
- **Aging** is in days at period end; an item is stale when older than the plan's rule (over 90
  days, C-01 §3 US-7.1).
- adjusted bank = balance per bank + deposits in transit - outstanding checks; adjusted book = book
  balance + unrecorded deposits - unrecorded withdrawals; difference = adjusted bank - adjusted
  book. "pending" when no statement is in yet (CLS-05 g), "tie" at 0.00, otherwise "off".
- `inputs_hash` is the SHA-256 of the canonical inputs and `content_hash` of the result, both
  stamped with `ENGINE_VERSION`: the same inputs always give the same hashes (a recompute that
  changes nothing is the same version's content).
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Final, Literal, cast

ENGINE_NAME: Final = "closes.reconciliation"
ENGINE_VERSION: Final = "1"
ENGINE_STAMP: Final = f"{ENGINE_NAME}/{ENGINE_VERSION}"  # reconciliations.engine_version

CENT: Final = Decimal("0.01")
ZERO: Final = Decimal("0.00")
STALE_AFTER_DAYS: Final = 90  # C-01 §3 US-7.1: "Stale > 90 days"
DATE_WINDOW_DAYS: Final = 7
CONFIDENCE_FLOOR: Final = Decimal("0.800")
AGING_BUCKETS: Final = ((0, 30, "0-30"), (31, 60, "31-60"), (61, 90, "61-90"))
AGING_OVER: Final = "over_90"

Side = Literal["bank", "book"]
Kind = Literal[
    "deposit_in_transit",
    "outstanding_check",
    "unrecorded_deposit",
    "unrecorded_withdrawal",
    "bank_error",
    "book_error",
]
Tally = Literal["pending", "tie", "off"]
MatchRule = Literal["reference", "amount_date", "carried_reference", "carried_amount_date"]

_ADDS: Final[frozenset[str]] = frozenset({"deposit_in_transit", "unrecorded_deposit"})
_CHECK_NO: Final = re.compile(r"(?:\bCHE?CK\b|\bCHK\b|#)\s*0*(\d{1,10})\b", re.I)
_AMOUNT: Final = re.compile(r"^\(?-?\$?\s*[\d,]+(?:\.\d{1,2})?\)?$")


class ReconciliationInvalid(ValueError):
    code = "reconciliation_invalid"


# --- inputs --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class StatementLine:
    """One transaction on the statement (`statement_lines`). Exactly one of withdrawal and
    deposit is set, both positive; `bbox` is the row's box on its page (fractions or points, as
    P-11 stored them)."""

    id: str
    txn_date: date
    description: str
    withdrawal: Decimal | None
    deposit: Decimal | None
    page_no: int = 1
    bbox: tuple[Decimal, Decimal, Decimal, Decimal] = (ZERO, ZERO, ZERO, ZERO)
    confidence: Decimal = Decimal(1)
    check_number: str | None = None

    @property
    def signed(self) -> Decimal:
        return self.deposit if self.deposit is not None else -(self.withdrawal or ZERO)

    @property
    def number(self) -> str | None:
        if self.check_number:
            return self.check_number.lstrip("#").lstrip("0") or "0"
        found = _CHECK_NO.search(self.description)
        return found.group(1).lstrip("0") or "0" if found else None


@dataclass(frozen=True)
class RegisterLine:
    """One line of the account's register in the ledger snapshot: signed (a deposit is positive,
    a payment negative). `ref` is the stable register line reference."""

    ref: str
    txn_date: date
    amount: Decimal
    number: str | None = None
    payee: str | None = None

    @property
    def check(self) -> str | None:
        return self.number.lstrip("#").lstrip("0") or "0" if self.number else None


@dataclass(frozen=True)
class PriorItem:
    """An item left open at the prior period's reconciliation (`reconciling_items`)."""

    id: str
    side: Side
    kind: Kind
    txn_date: date
    amount: Decimal
    ref: str | None = None
    register_line_ref: str | None = None


@dataclass(frozen=True)
class Inputs:
    period_end: date
    book_balance: Decimal
    balance_per_bank: Decimal | None  # None: no statement yet (CLS-05 g)
    statement_lines: Sequence[StatementLine] = ()
    register_lines: Sequence[RegisterLine] = ()
    prior_items: Sequence[PriorItem] = ()
    date_window_days: int = DATE_WINDOW_DAYS
    stale_after_days: int = STALE_AFTER_DAYS
    confidence_floor: Decimal = CONFIDENCE_FLOOR


# --- outputs -------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Pairing:
    statement_line_id: str
    register_line_ref: str
    match_rule: MatchRule


@dataclass(frozen=True)
class Item:
    side: Side
    kind: Kind
    txn_date: date
    amount: Decimal  # positive; the kind gives the sign
    days_at_period_end: int
    stale: bool
    aging: str
    ref: str | None = None
    statement_line_id: str | None = None
    register_line_ref: str | None = None
    carried_from: str | None = None

    @property
    def effect(self) -> Decimal:
        return self.amount if self.kind in _ADDS else -self.amount


@dataclass(frozen=True)
class Result:
    period_end: date
    balance_per_bank: Decimal | None
    deposits_in_transit: Decimal
    outstanding_checks: Decimal
    adjusted_bank: Decimal | None
    book_balance: Decimal
    unrecorded_deposits: Decimal
    unrecorded_withdrawals: Decimal
    adjusted_book: Decimal
    difference: Decimal | None
    tally: Tally
    items: tuple[Item, ...]
    matches: tuple[Pairing, ...]
    cleared_prior: tuple[str, ...]
    needs_review: tuple[str, ...]
    aging: Mapping[str, Decimal]
    engine_version: str
    inputs_hash: str
    content_hash: str
    stale_count: int = field(default=0)


# --- statement lines from P-11's extracted tables ------------------------------------------------


@dataclass(frozen=True)
class TableCell:
    """One cell of an `extracted_table_cells` row."""

    row_no: int
    col_no: int
    text: str
    bbox: tuple[Decimal, Decimal, Decimal, Decimal]
    confidence: Decimal


@dataclass(frozen=True)
class Columns:
    """Which column holds what (the statement layout's header row, read by the caller)."""

    date: int
    description: int
    withdrawal: int | None = None
    deposit: int | None = None
    amount: int | None = None  # one signed column instead of two
    check_number: int | None = None


def _money(text: str) -> Decimal | None:
    raw = text.strip().replace("$", "").replace(" ", "")
    if not raw or not _AMOUNT.match(raw):
        return None
    negative = raw.startswith("(") or raw.startswith("-")
    try:
        value = Decimal(raw.strip("()").lstrip("-").replace(",", "")).quantize(CENT)
    except InvalidOperation:
        return None
    return -value if negative else value


def _date(text: str, period_end: date) -> date | None:
    """A statement date as printed: MM/DD, MM/DD/YY or MM/DD/YYYY. A month after the period's
    month without a year belongs to the year before (a December line on a January statement)."""
    found = re.match(r"^\s*(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2}|\d{4}))?\s*$", text)
    if not found:
        return None
    month, day = int(found.group(1)), int(found.group(2))
    year_text = found.group(3)
    if year_text is None:
        year = period_end.year - (1 if month > period_end.month else 0)
    else:
        year = int(year_text) + (2000 if len(year_text) == 2 else 0)
    try:
        return date(year, month, day)
    except ValueError:
        return None


def statement_lines_from_table(
    table_id: str,
    page_no: int,
    cells: Iterable[TableCell],
    columns: Columns,
    period_end: date,
) -> tuple[StatementLine, ...]:
    """Each transaction row of one extracted table as a statement line: its date, description and
    amount from the mapped columns, the row's box (the union of its cells' boxes) and the lowest
    confidence of the cells it read. Rows without a readable date and amount (headers, totals,
    running-balance lines) are skipped; nothing is computed that the page does not print."""
    rows: dict[int, dict[int, TableCell]] = {}
    for cell in cells:
        rows.setdefault(cell.row_no, {})[cell.col_no] = cell
    out: list[StatementLine] = []
    for row_no in sorted(rows):
        row = rows[row_no]
        when_cell = row.get(columns.date)
        when = _date(when_cell.text, period_end) if when_cell else None
        if when is None:
            continue
        used: list[TableCell] = [c for c in (when_cell,) if c is not None]
        withdrawal = deposit = None
        if columns.amount is not None and columns.amount in row:
            value = _money(row[columns.amount].text)
            used.append(row[columns.amount])
            if value is not None and value != 0:
                deposit, withdrawal = (value, None) if value > 0 else (None, -value)
        else:
            if columns.withdrawal is not None and columns.withdrawal in row:
                w = _money(row[columns.withdrawal].text)
                if w:
                    withdrawal = abs(w)
                    used.append(row[columns.withdrawal])
            if columns.deposit is not None and columns.deposit in row:
                d = _money(row[columns.deposit].text)
                if d:
                    deposit = abs(d)
                    used.append(row[columns.deposit])
        if (withdrawal is None) == (deposit is None):
            continue
        described = row.get(columns.description)
        if described is not None:
            used.append(described)
        number_cell = row.get(columns.check_number) if columns.check_number is not None else None
        if number_cell is not None:
            used.append(number_cell)
        boxes = [c.bbox for c in used]
        bbox = (
            min(b[0] for b in boxes),
            min(b[1] for b in boxes),
            max(b[2] for b in boxes),
            max(b[3] for b in boxes),
        )
        out.append(
            StatementLine(
                id=f"{table_id}:{row_no}",
                txn_date=when,
                description=(described.text.strip() if described else "")[:500],
                withdrawal=withdrawal,
                deposit=deposit,
                page_no=page_no,
                bbox=bbox,
                confidence=min(c.confidence for c in used),
                check_number=(number_cell.text.strip() or None) if number_cell else None,
            )
        )
    return tuple(out)


# --- the engine ----------------------------------------------------------------------------------


def _q(value: Decimal) -> Decimal:
    return Decimal(value).quantize(CENT)


def _aging(days: int) -> str:
    for low, high, label in AGING_BUCKETS:
        if low <= days <= high:
            return label
    return AGING_OVER


def _text(value: object) -> object:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        return [_text(v) for v in cast("Sequence[object]", value)]
    if isinstance(value, dict):
        return {str(k): _text(v) for k, v in cast("Mapping[object, object]", value).items()}
    return value


def _digest(payload: object) -> str:
    body = json.dumps(
        {"engine": ENGINE_NAME, "version": ENGINE_VERSION, "body": _text(payload)},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def inputs_hash(inputs: Inputs) -> str:
    """The canonical inputs: order-independent (lines sorted by id/ref)."""
    return _digest(
        {
            "period_end": inputs.period_end,
            "book_balance": _q(inputs.book_balance),
            "balance_per_bank": None
            if inputs.balance_per_bank is None
            else _q(inputs.balance_per_bank),
            "statement": sorted(
                (
                    [
                        s.id,
                        s.txn_date,
                        _q(s.signed),
                        s.number or "",
                        format(Decimal(s.confidence), "f"),
                    ]
                    for s in inputs.statement_lines
                ),
                key=lambda r: str(r[0]),
            ),
            "register": sorted(
                ([r.ref, r.txn_date, _q(r.amount), r.check or ""] for r in inputs.register_lines),
                key=lambda r: str(r[0]),
            ),
            "prior": sorted(
                (
                    [p.id, p.side, p.kind, p.txn_date, _q(p.amount), p.register_line_ref or ""]
                    for p in inputs.prior_items
                ),
                key=lambda r: str(r[0]),
            ),
            "window": inputs.date_window_days,
            "stale_after": inputs.stale_after_days,
            "floor": format(Decimal(inputs.confidence_floor), "f"),
        }
    )


@dataclass
class _Candidate:
    key: str
    txn_date: date
    amount: Decimal  # signed, as it would show on the statement
    number: str | None
    prior: PriorItem | None = None
    register: RegisterLine | None = None


def _validate(inputs: Inputs) -> None:
    ids = [s.id for s in inputs.statement_lines]
    refs = [r.ref for r in inputs.register_lines]
    if len(set(ids)) != len(ids) or len(set(refs)) != len(refs):
        raise ReconciliationInvalid("duplicate statement line id or register line ref")
    for line in inputs.statement_lines:
        if (line.withdrawal is None) == (line.deposit is None):
            raise ReconciliationInvalid(f"statement line {line.id}: one of withdrawal, deposit")
        if (line.withdrawal or line.deposit or ZERO) <= 0:
            raise ReconciliationInvalid(f"statement line {line.id}: amounts are positive")
    for reg in inputs.register_lines:
        if reg.amount == 0:
            raise ReconciliationInvalid(f"register line {reg.ref}: zero amount")
    for prior in inputs.prior_items:
        if prior.amount <= 0:
            raise ReconciliationInvalid(f"prior item {prior.id}: amounts are positive")
    if inputs.date_window_days < 0 or inputs.stale_after_days < 0:
        raise ReconciliationInvalid("negative window")


def _prior_signed(prior: PriorItem) -> Decimal:
    """How a prior bank-side item would show on this period's statement."""
    return prior.amount if prior.kind == "deposit_in_transit" else -prior.amount


def _pair(
    statement: Sequence[StatementLine],
    candidates: list[_Candidate],
    window: int,
    floor: Decimal,
) -> tuple[list[tuple[StatementLine, _Candidate, str]], set[str], list[str]]:
    matched: list[tuple[StatementLine, _Candidate, str]] = []
    used_lines: set[str] = set()
    used_candidates: set[str] = set()
    needs_review = [s.id for s in statement if Decimal(s.confidence) < floor]
    eligible = [s for s in statement if Decimal(s.confidence) >= floor]
    # 1. reference: the check number and the amount; the statement never clears before issue.
    for line in sorted(eligible, key=lambda s: (s.txn_date, s.id)):
        number = line.number
        if number is None:
            continue
        for cand in candidates:
            if (
                cand.key not in used_candidates
                and cand.number == number
                and _q(cand.amount) == _q(line.signed)
                and line.txn_date >= cand.txn_date
            ):
                matched.append((line, cand, "reference"))
                used_lines.add(line.id)
                used_candidates.add(cand.key)
                break
    # 2. amount_date: same amount and direction within the window, nearest date first; a check
    # with a number only matches by reference.
    for line in sorted(eligible, key=lambda s: (s.txn_date, s.id)):
        if line.id in used_lines:
            continue
        best: _Candidate | None = None
        best_gap = window + 1
        for cand in candidates:
            if cand.key in used_candidates or _q(cand.amount) != _q(line.signed):
                continue
            if cand.number is not None and line.number is not None and cand.number != line.number:
                continue
            gap = abs((line.txn_date - cand.txn_date).days)
            if gap <= window and (gap, cand.key) < (best_gap, best.key if best else "~"):
                best, best_gap = cand, gap
        if best is not None:
            matched.append((line, best, "amount_date"))
            used_lines.add(line.id)
            used_candidates.add(best.key)
    return matched, used_candidates, needs_review


def reconcile(inputs: Inputs) -> Result:
    _validate(inputs)
    end = inputs.period_end
    in_period = [r for r in inputs.register_lines if r.txn_date <= end]
    statement = [s for s in inputs.statement_lines if s.txn_date <= end]

    # Prior book-side items clear when this period's register records them.
    cleared_prior: list[str] = []
    recorded_refs: set[str] = set()
    register_pool = list(in_period)
    for prior in sorted(inputs.prior_items, key=lambda p: (p.txn_date, p.id)):
        if prior.side != "book":
            continue
        signed = prior.amount if prior.kind == "unrecorded_deposit" else -prior.amount
        for reg in register_pool:
            if reg.ref not in recorded_refs and _q(reg.amount) == _q(signed):
                recorded_refs.add(reg.ref)
                cleared_prior.append(prior.id)
                break
    register_pool = [r for r in register_pool if r.ref not in recorded_refs]

    candidates: list[_Candidate] = [
        _Candidate(
            key=f"prior:{p.id}",
            txn_date=p.txn_date,
            amount=_prior_signed(p),
            number=(p.ref or "").lstrip("#").lstrip("0") or None
            if p.kind == "outstanding_check"
            else None,
            prior=p,
        )
        for p in inputs.prior_items
        if p.side == "bank" and p.kind in ("deposit_in_transit", "outstanding_check")
    ] + [
        _Candidate(
            key=f"reg:{r.ref}", txn_date=r.txn_date, amount=r.amount, number=r.check, register=r
        )
        for r in register_pool
    ]
    matched, used, needs_review = _pair(
        statement, candidates, inputs.date_window_days, Decimal(inputs.confidence_floor)
    )
    matched_lines = {line.id for line, _, _ in matched}
    matches: list[Pairing] = []
    for line, cand, rule in matched:
        if cand.prior is not None:
            cleared_prior.append(cand.prior.id)
            reg_ref = cand.prior.register_line_ref or f"prior:{cand.prior.id}"
            matches.append(Pairing(line.id, reg_ref, cast("MatchRule", f"carried_{rule}")))
        elif cand.register is not None:
            matches.append(Pairing(line.id, cand.register.ref, cast("MatchRule", rule)))

    def item(
        side: Side,
        kind: Kind,
        when: date,
        amount: Decimal,
        **kw: str | None,
    ) -> Item:
        days = max(0, (end - when).days)
        return Item(
            side=side,
            kind=kind,
            txn_date=when,
            amount=_q(abs(amount)),
            days_at_period_end=days,
            stale=days > inputs.stale_after_days,
            aging=_aging(days),
            **kw,
        )

    items: list[Item] = []
    has_statement = inputs.balance_per_bank is not None
    for cand in candidates:
        if cand.key in used:
            continue
        if cand.prior is not None:
            p = cand.prior
            items.append(
                item(
                    "bank",
                    p.kind,
                    p.txn_date,
                    p.amount,
                    ref=p.ref,
                    register_line_ref=p.register_line_ref,
                    carried_from=p.id,
                )
            )
            continue
        reg = cand.register
        if reg is None or not has_statement:
            continue  # book side only until the statement arrives (CLS-05 g)
        kind: Kind = "deposit_in_transit" if reg.amount > 0 else "outstanding_check"
        ref = f"#{reg.check}" if reg.check else None
        items.append(
            item("bank", kind, reg.txn_date, reg.amount, ref=ref, register_line_ref=reg.ref)
        )
    for prior in inputs.prior_items:
        if prior.side == "book" and prior.id not in cleared_prior:
            items.append(
                item(
                    "book",
                    prior.kind,
                    prior.txn_date,
                    prior.amount,
                    ref=prior.ref,
                    carried_from=prior.id,
                )
            )
    for line in statement:
        if line.id in matched_lines or line.id in needs_review:
            continue
        kind = "unrecorded_deposit" if line.deposit is not None else "unrecorded_withdrawal"
        items.append(
            item(
                "book",
                kind,
                line.txn_date,
                line.signed,
                ref=(f"#{line.number}" if line.number else None),
                statement_line_id=line.id,
            )
        )
    items.sort(key=lambda i: (i.side, i.kind, i.txn_date, i.ref or "", i.amount))

    def total(kind: str) -> Decimal:
        return _q(sum((i.amount for i in items if i.kind == kind), ZERO))

    dit, oc = total("deposit_in_transit"), total("outstanding_check")
    bank_errors = _q(sum((i.effect for i in items if i.kind == "bank_error"), ZERO))
    book_errors = _q(sum((i.effect for i in items if i.kind == "book_error"), ZERO))
    ud, uw = total("unrecorded_deposit"), total("unrecorded_withdrawal")
    book = _q(inputs.book_balance)
    adjusted_book = _q(book + ud - uw + book_errors)
    if inputs.balance_per_bank is None:
        bank = adjusted_bank = difference = None
        tally: Tally = "pending"
    else:
        bank = _q(inputs.balance_per_bank)
        adjusted_bank = _q(bank + dit - oc + bank_errors)
        difference = _q(adjusted_bank - adjusted_book)
        tally = "tie" if difference == 0 else "off"
    aging: dict[str, Decimal] = {label: ZERO for _, _, label in AGING_BUCKETS}
    aging[AGING_OVER] = ZERO
    for it in items:
        aging[it.aging] = _q(aging[it.aging] + it.amount)
    matches.sort(key=lambda m: (m.statement_line_id, m.register_line_ref))
    content = {
        "bank": bank,
        "adjusted_bank": adjusted_bank,
        "book": book,
        "adjusted_book": adjusted_book,
        "difference": difference,
        "tally": tally,
        "items": [
            [
                *(i.side, i.kind, i.txn_date, i.amount, i.ref or "", i.statement_line_id or ""),
                *(i.register_line_ref or "", i.carried_from or "", i.stale),
            ]
            for i in items
        ],
        "matches": [[m.statement_line_id, m.register_line_ref, m.match_rule] for m in matches],
        "review": sorted(needs_review),
    }
    return Result(
        period_end=end,
        balance_per_bank=bank,
        deposits_in_transit=dit,
        outstanding_checks=oc,
        adjusted_bank=adjusted_bank,
        book_balance=book,
        unrecorded_deposits=ud,
        unrecorded_withdrawals=uw,
        adjusted_book=adjusted_book,
        difference=difference,
        tally=tally,
        items=tuple(items),
        matches=tuple(matches),
        cleared_prior=tuple(sorted(cleared_prior)),
        needs_review=tuple(sorted(needs_review)),
        aging=aging,
        engine_version=ENGINE_STAMP,
        inputs_hash=inputs_hash(inputs),
        content_hash=_digest(content),
        stale_count=sum(1 for i in items if i.stale),
    )
