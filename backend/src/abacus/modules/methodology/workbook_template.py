"""The blank workbook v2 a firm downloads to fill in (K-01-T05; K-01 §3.2).

Headers only: the sheets and columns `parse_workbook` reads, required columns first. No firm
content (rule 16): what goes in it is the firm's, imported back through the workbook import.
Deterministic (ADR-042's pattern): fixed properties and ZIP entry stamps, so the same release
serves the same bytes.
"""

from __future__ import annotations

import io
import re
import zipfile
from datetime import UTC, datetime
from typing import Final, cast

from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.cell.cell import Cell
from openpyxl.styles import Font
from openpyxl.worksheet.worksheet import Worksheet

from abacus.modules.methodology.workbook import (
    AREAS,
    HEADERS,
    OPTIONAL_REQUEST_COLUMNS,
    PROGRAM_COLUMNS,
    PROGRAMS,
    REQUESTS,
    RULES,
    STEP_COLUMNS,
    STEP_OPTIONAL,
    STEP_OPTIONAL_LINKS,
    STEPS,
)

MEDIA_TYPE: Final = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
FILENAME: Final = "methodology-workbook-v2.xlsx"
_STAMP: Final = datetime(2026, 10, 27, tzinfo=UTC)
_ZIP_TIME: Final = (2026, 10, 27, 0, 0, 0)
_MODIFIED: Final = re.compile(rb"(<dcterms:modified[^>]*>)[^<]*(</dcterms:modified>)")
_BOLD: Final = Font(bold=True)
SHEETS: Final[tuple[tuple[str, tuple[str, ...]], ...]] = (
    (AREAS, HEADERS[AREAS]),
    (REQUESTS, (*HEADERS[REQUESTS], *OPTIONAL_REQUEST_COLUMNS)),
    (RULES, HEADERS[RULES]),
    (PROGRAMS, PROGRAM_COLUMNS),
    (STEPS, (*STEP_COLUMNS, *STEP_OPTIONAL, STEP_OPTIONAL_LINKS)),
)


def _normalised(raw: bytes) -> bytes:
    stamp = _STAMP.strftime("%Y-%m-%dT%H:%M:%SZ").encode()
    out = io.BytesIO()
    with (
        zipfile.ZipFile(io.BytesIO(raw)) as source,
        zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as target,
    ):
        for info in source.infolist():
            entry = zipfile.ZipInfo(info.filename, date_time=_ZIP_TIME)
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o644 << 16
            entry.create_system = 3
            data = source.read(info.filename)
            if info.filename == "docProps/core.xml":
                data = _MODIFIED.sub(lambda m: m.group(1) + stamp + m.group(2), data)
            target.writestr(entry, data)
    return out.getvalue()


def workbook_template() -> bytes:
    """The five sheets with their header rows, bold, nothing else."""
    workbook = Workbook(write_only=True)
    properties = workbook.properties
    properties.creator = "platform"
    properties.lastModifiedBy = "platform"
    properties.created = _STAMP.replace(tzinfo=None)
    properties.modified = _STAMP.replace(tzinfo=None)
    for name, columns in SHEETS:
        sheet = cast(Worksheet, workbook.create_sheet(name))
        row: list[Cell] = []
        for column in columns:
            cell = WriteOnlyCell(sheet, value=column)
            cell.font = _BOLD
            row.append(cell)
        sheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return _normalised(buffer.getvalue())


__all__ = ["FILENAME", "MEDIA_TYPE", "SHEETS", "workbook_template"]
