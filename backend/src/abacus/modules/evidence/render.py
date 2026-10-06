"""Deterministic trial balance rendering (ADR-042). PROTECTED. TASK-009 design §6.

Identical data → byte-identical files:
- lines are sorted by account code, then name;
- workbook properties are fixed (creator `platform`; created and modified = the pull time);
- the ZIP container is rebuilt with a fixed timestamp and fixed compression.

Account names come from the client's system and are hostile (AGENTS.md #8). They're written as
explicit strings, never interpreted as formulas. Totals are computed here (code computes,
ADR-050).
"""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import cast
from uuid import UUID

from openpyxl import Workbook
from openpyxl.cell.cell import Cell
from openpyxl.styles import Font
from openpyxl.worksheet.worksheet import Worksheet

MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_ZIP_TIME = (1980, 1, 1, 0, 0, 0)
_AMOUNT = "#,##0.00;-#,##0.00"
_BOLD = Font(bold=True)


@dataclass(frozen=True)
class TrialBalanceLine:
    account_code: str
    account_name: str
    debit: Decimal
    credit: Decimal


@dataclass(frozen=True)
class TrialBalance:
    """A validated trial balance (TASK-010's ledger snapshot maps onto this)."""

    client_entity_id: UUID
    entity_name: str
    period_start: date
    period_end: date
    pulled_at: datetime
    snapshot_id: UUID
    source: str
    source_fingerprint: str
    lines: tuple[TrialBalanceLine, ...]


_MAX_CELL = 32_767  # Excel's limit; longer values would corrupt the file
_FORMULA_LEADS = ("=", "+", "-", "@")


def _text(sheet: Worksheet, row: int, column: int, value: str) -> None:
    if len(value) > _MAX_CELL:
        raise ValueError("text longer than a spreadsheet cell can hold")
    cell = cast(Cell, sheet.cell(row=row, column=column))
    cell.value = value
    cell.data_type = "s"  # always a string: a leading "=" never becomes a formula
    if value.startswith(_FORMULA_LEADS):
        cell.quotePrefix = True  # and stays text if copied or exported elsewhere


def _amount(sheet: Worksheet, row: int, column: int, value: Decimal) -> None:
    if not value.is_finite():
        raise ValueError("amounts must be finite")
    cell = cast(Cell, sheet.cell(row=row, column=column))
    cell.value = value
    cell.number_format = _AMOUNT


def _utc(moment: datetime) -> datetime:
    """Naive datetimes would be read in the host's zone, so output would vary by machine."""
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError("pulled_at must be timezone-aware")
    return moment.astimezone(UTC)


def _workbook(tb: TrialBalance) -> Workbook:
    pulled_at = _utc(tb.pulled_at)
    workbook = Workbook()
    sheet = cast(Worksheet, workbook.active)
    sheet.title = "Trial balance"
    for column, header in enumerate(("Account", "Name", "Debit", "Credit"), start=1):
        _text(sheet, 1, column, header)
        cast(Cell, sheet.cell(row=1, column=column)).font = _BOLD
    lines = sorted(tb.lines, key=lambda line: (line.account_code, line.account_name))
    row = 2
    for line in lines:
        _text(sheet, row, 1, line.account_code)
        _text(sheet, row, 2, line.account_name)
        _amount(sheet, row, 3, line.debit)
        _amount(sheet, row, 4, line.credit)
        row += 1
    _text(sheet, row, 2, "Total")
    _amount(sheet, row, 3, sum((line.debit for line in lines), Decimal(0)))
    _amount(sheet, row, 4, sum((line.credit for line in lines), Decimal(0)))
    row += 2
    footer = (
        ("Source", tb.source),
        ("Method", "retrieved"),
        ("Pulled at", pulled_at.isoformat()),
        ("Period", f"{tb.period_start.isoformat()} to {tb.period_end.isoformat()}"),
        ("Entity", tb.entity_name),
        ("Entity ID", str(tb.client_entity_id)),
        ("Snapshot ID", str(tb.snapshot_id)),
        ("Source fingerprint", tb.source_fingerprint),
    )
    for label, value in footer:
        _text(sheet, row, 1, label)
        _text(sheet, row, 2, value)
        row += 1
    for letter, width in (("A", 16), ("B", 48), ("C", 18), ("D", 18)):
        sheet.column_dimensions[letter].width = width
    properties = workbook.properties
    properties.creator = "platform"
    properties.lastModifiedBy = "platform"
    properties.created = pulled_at.replace(tzinfo=None)
    properties.modified = pulled_at.replace(tzinfo=None)
    return workbook


_MODIFIED = re.compile(rb"(<dcterms:modified[^>]*>)[^<]*(</dcterms:modified>)")


def _normalised(raw: bytes, pulled_at: datetime) -> bytes:
    """Rebuild the ZIP with fixed entry timestamps, attributes and compression. openpyxl stamps
    the save time into `dcterms:modified`; it is set back to the pull time here."""
    stamp = _utc(pulled_at).strftime("%Y-%m-%dT%H:%M:%SZ").encode()
    out = io.BytesIO()
    with (
        zipfile.ZipFile(io.BytesIO(raw)) as source,
        zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as target,
    ):
        for info in source.infolist():
            entry = zipfile.ZipInfo(info.filename, date_time=_ZIP_TIME)
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o644 << 16
            entry.create_system = 3  # the same on every platform
            data = source.read(info.filename)
            if info.filename == "docProps/core.xml":
                data, count = _MODIFIED.subn(lambda m: m.group(1) + stamp + m.group(2), data)
                if count != 1:
                    raise RuntimeError("docProps/core.xml has no modified stamp to pin")
            target.writestr(entry, data)
    return out.getvalue()


def render_trial_balance(tb: TrialBalance) -> bytes:
    buffer = io.BytesIO()
    _workbook(tb).save(buffer)
    return _normalised(buffer.getvalue(), tb.pulled_at)
