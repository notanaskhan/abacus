"""Deterministic, injection-safe workbooks (A-06-T29; ADR-042). Same rows, same bytes.

Client and firm text reaches a spreadsheet as text, never as a formula: a string starting with `=`,
`+`, `-`, `@`, a tab or a carriage return gets a leading apostrophe. A number stays a number. The
workbook's clock and zip times are fixed, because openpyxl stamps the save time whatever it's told.
"""

from __future__ import annotations

import io
import re
import zipfile
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Final, cast

from openpyxl import Workbook
from openpyxl.worksheet.worksheet import Worksheet

Cell = str | int | Decimal | bool | None
XLSX: Final = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_FORMULA_LEAD: Final = ("=", "+", "-", "@", "\t", "\r")
_EPOCH: Final = datetime(2026, 1, 1)
_ZIP_TIME: Final = (1980, 1, 1, 0, 0, 0)
_MODIFIED: Final = re.compile(rb"(<dcterms:modified[^>]*>)[^<]*(</dcterms:modified>)")
_STAMP: Final = _EPOCH.strftime("%Y-%m-%dT%H:%M:%SZ").encode()


def safe_text(value: str) -> str:
    """A string that a spreadsheet can't evaluate."""
    return f"'{value}" if value.startswith(_FORMULA_LEAD) else value


@dataclass(frozen=True)
class Sheet:
    title: str
    rows: Sequence[Sequence[Cell]]


def _safe(cell: Cell) -> object:
    if isinstance(cell, str):
        return safe_text(cell)
    if isinstance(cell, Decimal):
        return float(cell) if cell == cell.to_integral_value() else str(cell)
    return cell


def workbook(sheets: Sequence[Sheet]) -> bytes:
    book = Workbook(write_only=True)
    book.properties.creator = "platform"
    book.properties.lastModifiedBy = "platform"
    book.properties.created = _EPOCH
    book.properties.modified = _EPOCH
    for sheet in sheets:
        target = cast(Worksheet, book.create_sheet(sheet.title))
        for row in sheet.rows:
            target.append([_safe(cell) for cell in row])
    buffer = io.BytesIO()
    book.save(buffer)
    return _normalised(buffer.getvalue())


def _normalised(data: bytes) -> bytes:
    out = io.BytesIO()
    with (
        zipfile.ZipFile(io.BytesIO(data)) as source,
        zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as target,
    ):
        for name in sorted(source.namelist()):
            content = source.read(name)
            if name == "docProps/core.xml":
                content = _MODIFIED.sub(rb"\g<1>" + _STAMP + rb"\g<2>", content)
            target.writestr(zipfile.ZipInfo(name, date_time=_ZIP_TIME), content)
    return out.getvalue()
