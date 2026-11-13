"""Deterministic xlsx of a designed workbook, "Open in Excel" (T-05-T57; TASK-7905; ADR P-69 /
ADR-237, ADR-042, ADR-052; DEC-4908). Amber.

The caller (an owner such as `tax`) hands sheets of cells; this module writes them and nothing
else, on the evidence `render.py` pattern:

- **Formulas** are written only from the closed grammar (`compute.formula`): each is parsed and
  rendered back canonically, sheet references mapped to the workbook's sheet names, and stored as
  a live formula (Excel computes it on open). A formula outside the grammar is never written as a
  formula: the cell gets its stored value instead.
- **Text** is always a string cell (`data_type` "s"): a value that would lead as a formula (`=`,
  `+`, `-`, `@`, tab, carriage return, or their full-width forms) also gets Excel's quote prefix,
  so a client string starting with `=` stays text in Excel and anywhere it is copied (ADR-052).
- **Numbers** are decimals, written as numbers with a fixed number format.
- **Byte-identical output** for identical data: fixed workbook properties (creator `platform`,
  created and modified at `STAMP`), sheets and cells written in a fixed order, and the ZIP rebuilt
  with fixed entry times, attributes and compression.
"""

from __future__ import annotations

import io
import re
import unicodedata
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Final, cast

from openpyxl import Workbook
from openpyxl.cell.cell import Cell
from openpyxl.utils.cell import coordinate_from_string

from abacus.modules.workpapers.compute.formula import FormulaError, parse, render

STAMP: Final = datetime(2000, 1, 1, tzinfo=UTC)  # the file's fixed created and modified time
_ZIP_TIME: Final = (1980, 1, 1, 0, 0, 0)
_AMOUNT: Final = "#,##0.00;(#,##0.00)"
_MAX_CELL: Final = 32_767
_FORMULA_LEADS: Final = ("=", "+", "-", "@", "\t", "\r")
_MODIFIED: Final = re.compile(rb"(<dcterms:modified[^>]*>)[^<]*(</dcterms:modified>)")
# A sheet reference in the canonical text: `05!` or `'05'!` (the renderer quotes it).
_SHEET_REF: Final = re.compile(r"(?<![A-Za-z0-9_'])('?)(\d{2})\1!")
MAX_TITLE: Final = 31  # Excel's sheet-name limit


@dataclass(frozen=True)
class ExportCell:
    """One cell: its stored value (a decimal, text, or None) and, when it has one, the formula
    text as the workbook stores it."""

    a1: str
    value: Decimal | str | None
    formula: str | None = None


@dataclass(frozen=True)
class ExportSheet:
    key: str  # "05"
    title: str  # "05 Capital": the xlsx sheet name
    cells: tuple[ExportCell, ...]


def formula_like(value: str) -> bool:
    return unicodedata.normalize("NFKC", value).startswith(_FORMULA_LEADS) or value.startswith(
        _FORMULA_LEADS
    )


def sheet_name(title: str) -> str:
    """An Excel-safe sheet name (no `[]:*?/\\`, at most 31 characters)."""
    cleaned = re.sub(r"[\[\]:*?/\\]", " ", title).strip() or "Sheet"
    return cleaned[:MAX_TITLE]


def excel_formula(text: str, own: str, names: Mapping[str, str]) -> str | None:
    """The canonical formula for Excel, references mapped from `05!` to `'05 Capital'!`; None
    when the text is outside the closed grammar (never written as a formula)."""
    try:
        canonical = render(parse(text), own_sheet=own)
    except FormulaError:
        return None

    def quoted(m: re.Match[str]) -> str:
        name = names.get(m.group(2))
        return m.group(0) if name is None else "'" + name.replace("'", "''") + "'!"

    return _SHEET_REF.sub(quoted, canonical)


def _text(cell: Cell, value: str) -> None:
    if len(value) > _MAX_CELL:
        value = value[:_MAX_CELL]
    cell.value = value
    cell.data_type = "s"  # always a string: a leading "=" never becomes a formula
    if formula_like(value):
        cell.quotePrefix = True


def _sort_key(a1: str) -> tuple[int, str]:
    letters, row = coordinate_from_string(a1)
    return int(row), f"{len(letters):02d}{letters}"


def build(sheets: Sequence[ExportSheet]) -> Workbook:
    workbook = Workbook()
    default = workbook.active
    if default is not None:
        workbook.remove(default)
    names = {s.key: sheet_name(s.title) for s in sheets}
    for s in sheets:
        sheet = workbook.create_sheet(names[s.key])
        for c in sorted(s.cells, key=lambda c: _sort_key(c.a1)):
            cell = cast(Cell, sheet[c.a1])
            formula = None if c.formula is None else excel_formula(c.formula, s.key, names)
            if formula is not None:
                cell.value = formula
                cell.data_type = "f"
                cell.number_format = _AMOUNT
            elif isinstance(c.value, Decimal):
                if not c.value.is_finite():
                    continue
                cell.value = c.value
                cell.number_format = _AMOUNT
            elif isinstance(c.value, str):
                _text(cell, c.value)
    properties = workbook.properties
    properties.creator = "platform"
    properties.lastModifiedBy = "platform"
    properties.created = STAMP.replace(tzinfo=None)
    properties.modified = STAMP.replace(tzinfo=None)
    return workbook


def _normalised(raw: bytes) -> bytes:
    stamp = STAMP.strftime("%Y-%m-%dT%H:%M:%SZ").encode()
    out = io.BytesIO()
    with (
        zipfile.ZipFile(io.BytesIO(raw)) as source,
        zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as target,
    ):
        for info in sorted(source.infolist(), key=lambda i: i.filename):
            entry = zipfile.ZipInfo(info.filename, date_time=_ZIP_TIME)
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o644 << 16
            entry.create_system = 3
            data = source.read(info.filename)
            if info.filename == "docProps/core.xml":
                data, count = _MODIFIED.subn(lambda m: m.group(1) + stamp + m.group(2), data)
                if count != 1:
                    raise RuntimeError("docProps/core.xml has no modified stamp to pin")
            target.writestr(entry, data)
    return out.getvalue()


def render_workbook(sheets: Sequence[ExportSheet]) -> bytes:
    """The xlsx bytes (module docstring): identical sheets give identical bytes."""
    buffer = io.BytesIO()
    build(sheets).save(buffer)
    return _normalised(buffer.getvalue())


__all__ = [
    "STAMP",
    "ExportCell",
    "ExportSheet",
    "build",
    "excel_formula",
    "formula_like",
    "render_workbook",
    "sheet_name",
]
