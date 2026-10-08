"""Request-list workbooks (SPEC-018): any firm's layout, read by column position (TASK-033 D1).

Hostile input (ADR-052): opened read-only with cached values (formulas never evaluated), bounded
(Q4), and problems are reported as sheet, row, column and a fixed code, never a cell's contents.
"""

from __future__ import annotations

import io
import re
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Final, cast

from openpyxl import Workbook, load_workbook
from openpyxl.worksheet._read_only import ReadOnlyWorksheet

MAX_BYTES: Final = 5 * 1024 * 1024
MAX_ROWS: Final = 2000
MAX_DESCRIPTION: Final = 2000
MAX_AREA: Final = 100
SAMPLE_ROWS: Final = 20
TIERS: Final = frozenset("ABCDE")
_SPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class Problem:
    sheet: str | None
    row: int | None
    column: str | None
    code: str


class RequestListInvalid(Exception):
    def __init__(self, problems: list[Problem]) -> None:
        super().__init__(f"{len(problems)} problem(s)")
        self.problems = problems[:100]


@dataclass(frozen=True)
class SheetPreview:
    name: str
    headers: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    suggested_description: int | None
    suggested_area: int | None
    suggested_tier: int | None


@dataclass(frozen=True)
class Row:
    number: int
    description: str
    area: str
    tier: str | None


def normalise(text: str) -> str:
    return _SPACE.sub(" ", text).strip().casefold()


def cell_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return _SPACE.sub(" ", str(value)).strip()


def column_name(index: int) -> str:
    name = ""
    index += 1
    while index:
        index, rest = divmod(index - 1, 26)
        name = chr(65 + rest) + name
    return name


def _open(data: bytes) -> Workbook:
    if len(data) > MAX_BYTES:
        raise RequestListInvalid([Problem(None, None, None, "too_large")])
    try:
        return load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception:
        raise RequestListInvalid([Problem(None, None, None, "not_a_workbook")]) from None


def _rows(workbook: Workbook, sheet: str) -> Iterator[tuple[object, ...]]:
    found = cast(ReadOnlyWorksheet, workbook[sheet])
    return iter(found.iter_rows(values_only=True))


def _suggest(headers: tuple[str, ...], words: tuple[str, ...]) -> int | None:
    for index, header in enumerate(headers):
        if any(word in header.casefold() for word in words):
            return index
    return None


def preview(data: bytes, header_row: int = 1) -> list[SheetPreview]:
    """Each sheet's headers (from `header_row`), up to 20 data rows, and suggested columns."""
    workbook = _open(data)
    try:
        sheets: list[SheetPreview] = []
        for name in workbook.sheetnames:
            raw = list(_head(_rows(workbook, name), header_row + SAMPLE_ROWS))
            header_cells = raw[header_row - 1] if len(raw) >= header_row else ()
            width = max([len(header_cells), *(len(r) for r in raw[header_row:])], default=0)
            headers = tuple(
                cell_text(header_cells[i])
                if i < len(header_cells) and cell_text(header_cells[i])
                else f"Column {column_name(i)}"
                for i in range(width)
            )
            samples = tuple(
                tuple(cell_text(r[i]) if i < len(r) else "" for i in range(width))
                for r in raw[header_row:]
                if any(cell_text(v) for v in r)
            )
            sheets.append(
                SheetPreview(
                    name,
                    headers,
                    samples,
                    _suggest(headers, ("request", "description", "item", "document")),
                    _suggest(headers, ("area", "section", "category", "cycle")),
                    _suggest(headers, ("tier",)),
                )
            )
        return sheets
    finally:
        workbook.close()


def _head(rows: Iterator[tuple[object, ...]], count: int) -> Iterator[tuple[object, ...]]:
    for index, row in enumerate(rows):
        if index >= count:
            return
        yield row


def _cell(values: tuple[object, ...], index: int | None) -> str:
    return cell_text(values[index]) if index is not None and index < len(values) else ""


def read_rows(
    data: bytes, sheet: str, header_row: int, description: int, area: int, tier: int | None
) -> tuple[list[Row], int]:
    """Every data row under `header_row` as (description, area, tier), and how many were empty.
    `RequestListInvalid` with every problem; nothing is partly read."""
    workbook = _open(data)
    problems: list[Problem] = []
    rows: list[Row] = []
    empty = 0
    try:
        if sheet not in workbook.sheetnames:
            raise RequestListInvalid([Problem(sheet, None, None, "missing_sheet")])
        for number, values in enumerate(_rows(workbook, sheet), start=1):
            if number <= header_row:
                continue

            text = _cell(values, description)
            area_text = _cell(values, area)
            tier_text = _cell(values, tier).upper()
            if not text:
                empty += 1
                continue
            if len(rows) >= MAX_ROWS:
                problems.append(Problem(sheet, None, None, "too_many_rows"))
                break
            if len(text) > MAX_DESCRIPTION:
                problems.append(Problem(sheet, number, column_name(description), "too_long"))
                continue
            if len(area_text) > MAX_AREA:
                problems.append(Problem(sheet, number, column_name(area), "too_long"))
                continue
            rows.append(Row(number, text, area_text, tier_text if tier_text in TIERS else None))
    finally:
        workbook.close()
    if problems:
        raise RequestListInvalid(problems)
    return rows, empty
