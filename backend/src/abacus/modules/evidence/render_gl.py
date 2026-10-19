"""Deterministic general ledger and journal listing workbooks (SPEC-034; TASK-070; ADR-042).
PROTECTED.

Written in streaming mode (a ledger may have 750,000 lines): rows go straight to the file, and
detail continues on "Detail (2)" and so on before Excel's row limit. Identical data gives
byte-identical files: fixed order, fixed properties, and the ZIP rebuilt with fixed timestamps
(`render._normalised`). Every text cell is an explicit string, never a formula (client text is
hostile); totals and differences are computed here (ADR-050).
"""

from __future__ import annotations

import io
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Final, cast
from uuid import UUID

from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.cell.cell import Cell
from openpyxl.styles import Font
from openpyxl.worksheet.worksheet import Worksheet

from abacus.modules.evidence.render import (
    _normalised as normalised,  # pyright: ignore[reportPrivateUsage] -- the same determinism
)
from abacus.modules.evidence.render import (
    _utc as utc,  # pyright: ignore[reportPrivateUsage] -- the same timezone rule
)
from abacus.modules.ledger.api import journals  # TASK-077 D1: one grouping

# openpyxl's write-only sheet has untyped stubs; it appends rows as `Worksheet` does.
Sheet = Worksheet


def _sheet(workbook: Workbook, title: str) -> Sheet:
    return cast(Worksheet, workbook.create_sheet(title))


EXCEL_ROWS: Final = 1_048_576
_MAX_CELL: Final = 32_767
_FORMULA_LEADS: Final = ("=", "+", "-", "@")
_AMOUNT: Final = "#,##0.00;-#,##0.00"
_BOLD: Final = Font(bold=True)


@dataclass(frozen=True)
class GlHeader:
    client_entity_id: UUID
    entity_name: str
    period_start: date
    period_end: date
    uploaded_at: datetime
    snapshot_id: UUID
    source: str
    source_fingerprint: str
    notes: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class GlBalanceRow:
    account_code: str
    account_name: str
    opening: Decimal
    debit: Decimal
    credit: Decimal
    closing: Decimal
    tb_closing: Decimal
    opening_derived: bool


@dataclass(frozen=True)
class GlEntryRow:
    line_no: int
    account_code: str
    posted_on: date
    kind: str | None
    reference: str | None
    counterparty: str | None
    description: str | None
    debit: Decimal
    credit: Decimal


def _text(sheet: Sheet, value: str, *, bold: bool = False) -> Cell:
    if len(value) > _MAX_CELL:
        raise ValueError("text longer than a spreadsheet cell can hold")
    cell = WriteOnlyCell(sheet, value=value)
    cell.data_type = "s"  # always a string: a leading "=" never becomes a formula
    if value.startswith(_FORMULA_LEADS):
        cell.quotePrefix = True
    if bold:
        cell.font = _BOLD
    return cell


def _amount(sheet: Sheet, value: Decimal, *, bold: bool = False) -> Cell:
    if not value.is_finite():
        raise ValueError("amounts must be finite")
    cell = WriteOnlyCell(sheet)
    cell.value = value  # a Decimal, kept exact
    cell.number_format = _AMOUNT
    if bold:
        cell.font = _BOLD
    return cell


def _blank(sheet: Sheet) -> Cell:
    return WriteOnlyCell(sheet, value=None)


def _workbook(header: GlHeader) -> Workbook:
    workbook = Workbook(write_only=True)
    moment = utc(header.uploaded_at).replace(tzinfo=None)
    properties = workbook.properties
    properties.creator = "platform"
    properties.lastModifiedBy = "platform"
    properties.created = moment
    properties.modified = moment
    return workbook


def _footer(sheet: Sheet, header: GlHeader) -> None:
    sheet.append([])
    for label, value in (
        ("Source", header.source),
        ("Method", "imported"),
        ("Uploaded at", utc(header.uploaded_at).isoformat()),
        ("Period", f"{header.period_start.isoformat()} to {header.period_end.isoformat()}"),
        ("Entity", header.entity_name),
        ("Entity ID", str(header.client_entity_id)),
        ("Snapshot ID", str(header.snapshot_id)),
        ("Source fingerprint", header.source_fingerprint),
        *header.notes,
    ):
        sheet.append([_text(sheet, label), _text(sheet, value)])


def _finish(workbook: Workbook, header: GlHeader) -> bytes:
    buffer = io.BytesIO()
    workbook.save(buffer)
    return normalised(buffer.getvalue(), header.uploaded_at)


class _Sheets:
    """Detail sheets that continue on a new one before the row limit, each with its header."""

    def __init__(
        self, workbook: Workbook, title: str, headers: Sequence[str], max_rows: int
    ) -> None:
        self.workbook, self.title, self.headers, self.max_rows = workbook, title, headers, max_rows
        self.count = 0
        self.rows = 0
        self.sheet = self._next()

    def _next(self) -> Sheet:
        self.count += 1
        name = self.title if self.count == 1 else f"{self.title} ({self.count})"
        sheet = _sheet(self.workbook, name)
        sheet.append([_text(sheet, h, bold=True) for h in self.headers])
        self.rows = 1
        return sheet

    def room(self, rows: int) -> Sheet:
        if self.rows + rows > self.max_rows:
            self.sheet = self._next()
        self.rows += rows
        return self.sheet


def render_general_ledger(
    header: GlHeader,
    balances: Sequence[GlBalanceRow],
    entries: Iterable[GlEntryRow],
    names: Mapping[str, str],
    *,
    max_rows: int = EXCEL_ROWS,
) -> bytes:
    """ "Reconciliation" (every account rolling forward to the trial balance), then the detail in
    line order (the export's account by account order)."""
    workbook = _workbook(header)
    recon = _sheet(workbook, "Reconciliation")
    recon.append(
        [
            _text(recon, h, bold=True)
            for h in (
                "Account",
                "Name",
                "Opening",
                "Debits",
                "Credits",
                "Closing",
                "Trial balance",
                "Difference",
                "Note",
            )
        ]
    )
    totals = [Decimal(0)] * 6
    for b in sorted(balances, key=lambda x: (x.account_code, x.account_name)):
        difference = b.closing - b.tb_closing
        recon.append(
            [
                _text(recon, b.account_code),
                _text(recon, b.account_name),
                _amount(recon, b.opening),
                _amount(recon, b.debit),
                _amount(recon, b.credit),
                _amount(recon, b.closing),
                _amount(recon, b.tb_closing),
                _amount(recon, difference),
                _text(recon, "Opening derived" if b.opening_derived else ""),
            ]
        )
        for i, value in enumerate(
            (b.opening, b.debit, b.credit, b.closing, b.tb_closing, difference)
        ):
            totals[i] += value
    recon.append(
        [_blank(recon), _text(recon, "Total", bold=True)]
        + [_amount(recon, t, bold=True) for t in totals]
    )
    _footer(recon, header)
    detail = _Sheets(
        workbook,
        "Detail",
        (
            "Account",
            "Name",
            "Date",
            "Type",
            "Reference",
            "Name or party",
            "Description",
            "Debit",
            "Credit",
        ),
        max_rows,
    )
    for e in entries:
        sheet = detail.room(1)
        sheet.append(_entry_cells(sheet, e, names))
    return _finish(workbook, header)


def _entry_cells(sheet: Sheet, e: GlEntryRow, names: Mapping[str, str]) -> list[Cell]:
    return [
        _text(sheet, e.account_code),
        _text(sheet, names.get(e.account_code, "")),
        _text(sheet, e.posted_on.isoformat()),
        _text(sheet, e.kind or ""),
        _text(sheet, e.reference or ""),
        _text(sheet, e.counterparty or ""),
        _text(sheet, e.description or ""),
        _amount(sheet, e.debit),
        _amount(sheet, e.credit),
    ]


def render_journal_listing(
    header: GlHeader,
    entries: Iterable[GlEntryRow],
    names: Mapping[str, str],
    *,
    max_rows: int = EXCEL_ROWS,
) -> bytes:
    """One block per transaction: its date, type, reference and name, then its lines and totals;
    a block whose debits and credits differ is marked (informational, D2)."""
    workbook = _workbook(header)
    sheets = _Sheets(
        workbook,
        "Journals",
        (
            "Date",
            "Type",
            "Reference",
            "Name or party",
            "Account",
            "Account name",
            "Debit",
            "Credit",
            "Note",
        ),
        max_rows,
    )
    count = 0
    for (on, kind, reference, party), lines in journals(entries):
        count += 1
        sheet = sheets.room(len(lines) + 1)
        debit = sum((x.debit for x in lines), Decimal(0))
        credit = sum((x.credit for x in lines), Decimal(0))
        for i, e in enumerate(lines):
            sheet.append(
                [
                    _text(sheet, on if i == 0 else ""),
                    _text(sheet, kind if i == 0 else ""),
                    _text(sheet, reference if i == 0 else ""),
                    _text(sheet, (party or e.counterparty or "") if i == 0 else ""),
                    _text(sheet, e.account_code),
                    _text(sheet, names.get(e.account_code, "")),
                    _amount(sheet, e.debit),
                    _amount(sheet, e.credit),
                    _blank(sheet),
                ]
            )
        sheet.append(
            [_blank(sheet)] * 5
            + [
                _text(sheet, "Total", bold=True),
                _amount(sheet, debit, bold=True),
                _amount(sheet, credit, bold=True),
                _text(sheet, "" if debit == credit else "Doesn't balance on its own"),
            ]
        )
    summary = _sheet(workbook, "About")
    summary.append([_text(summary, "Transactions"), _amount(summary, Decimal(count))])
    _footer(summary, header)
    return _finish(workbook, header)
