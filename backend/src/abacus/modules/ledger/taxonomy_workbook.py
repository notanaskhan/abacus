"""A firm's grouping set from a workbook (A-03-T06; A-03 F5 US-5.1; SPEC-580 AC-17).

"BH FS groupings v1.xlsx" carries three sheets: Groupings (grouping_key, grouping_label, class),
FS lines (fs_line_key, fs_line_label, grouping_key, normal_balance) and Number ranges
(account_from, account_to, fs_line_key). Every problem names its sheet, row and code:
`sheet_missing`, `header`, `missing_key`, `class_invalid`, `normal_balance_invalid`,
`duplicate_key`, `unknown_grouping`, `unknown_fs_line`, `range_invalid`, `overlapping_range`,
`too_many_rows`, `workbook_unreadable`. A draft with any problem keeps no rows (as the CSV path).

Cells are read as values, never evaluated: a cell that begins with `=`, `+`, `-` or `@` is text
(client and firm files are hostile input, ADR-052, ADR-064).
"""

from __future__ import annotations

import io
from collections.abc import Iterator
from typing import Final
from zipfile import BadZipFile

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

from abacus.modules.ledger.mapping import (
    CLASSES,
    MAX_ROWS,
    ParsedGrouping,
    ParsedGroupingSet,
    ParsedLine,
    Problem,
    account_key,
    finish_grouping_set,
)

GROUPINGS: Final = "Groupings"
FS_LINES: Final = "FS lines"
RANGES: Final = "Number ranges"
HEADERS: Final = {
    GROUPINGS: ("grouping_key", "grouping_label", "class"),
    FS_LINES: ("fs_line_key", "fs_line_label", "grouping_key", "normal_balance"),
    RANGES: ("account_from", "account_to", "fs_line_key"),
}
MAX_BYTES: Final = 2_000_000


def _text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _rows(
    sheet: str, raw: list[tuple[object, ...]], problems: list[Problem]
) -> Iterator[tuple[int, list[str]]]:
    width = len(HEADERS[sheet])
    if not raw or tuple(_text(c).lower() for c in raw[0][:width]) != HEADERS[sheet]:
        problems.append(Problem(1, "header", ",".join(HEADERS[sheet]), sheet))
        return
    if len(raw) - 1 > MAX_ROWS:
        problems.append(Problem(MAX_ROWS + 2, "too_many_rows", str(MAX_ROWS), sheet))
    for number, row in enumerate(raw[1 : MAX_ROWS + 1], start=2):
        cells = [_text(c) for c in row[:width]] + [""] * (width - len(row))
        if any(cells):
            yield number, cells


def parse_grouping_workbook(data: bytes) -> ParsedGroupingSet:
    """A grouping set from the three-sheet workbook, with every problem by sheet, row and code."""
    empty = ParsedGroupingSet([], [], [], [], "0" * 64)
    if len(data) > MAX_BYTES:
        return ParsedGroupingSet([], [], [], [Problem(0, "too_large", str(MAX_BYTES))], "0" * 64)
    try:
        book = load_workbook(io.BytesIO(data), read_only=True, data_only=True, keep_vba=False)
    except (InvalidFileException, BadZipFile, KeyError, OSError, ValueError, TypeError):
        return ParsedGroupingSet([], [], [], [Problem(0, "workbook_unreadable", "")], "0" * 64)
    problems: list[Problem] = []
    sheets: dict[str, list[tuple[object, ...]]] = {}
    for name in HEADERS:
        if name not in book.sheetnames:
            problems.append(Problem(1, "sheet_missing", name, name))
            continue
        sheets[name] = [tuple(r) for r in book[name].iter_rows(values_only=True)]
    book.close()
    if problems:
        return ParsedGroupingSet(empty.groupings, empty.lines, [], problems, empty.payload_hash)

    groupings: dict[str, ParsedGrouping] = {}
    for number, (key, label, cls) in _rows(GROUPINGS, sheets[GROUPINGS], problems):
        if not key:
            problems.append(Problem(number, "missing_key", "grouping_key", GROUPINGS))
        elif cls.lower() not in CLASSES:
            problems.append(Problem(number, "class_invalid", cls, GROUPINGS))
        elif key in groupings:
            problems.append(Problem(number, "duplicate_key", key, GROUPINGS))
        else:
            groupings[key] = ParsedGrouping(key, label or key, cls.lower())

    lines: dict[str, ParsedLine] = {}
    for number, (key, label, grouping, normal) in _rows(FS_LINES, sheets[FS_LINES], problems):
        if not key or not grouping:
            problems.append(
                Problem(number, "missing_key", "fs_line_key and grouping_key", FS_LINES)
            )
        elif grouping not in groupings:
            problems.append(Problem(number, "unknown_grouping", grouping, FS_LINES))
        elif normal.lower() not in ("debit", "credit"):
            problems.append(Problem(number, "normal_balance_invalid", normal, FS_LINES))
        elif key in lines:
            problems.append(Problem(number, "duplicate_key", key, FS_LINES))
        else:
            lines[key] = ParsedLine(key, label or key, grouping, normal.lower())

    ranges: list[tuple[str, str, str]] = []
    range_rows: list[int] = []
    for number, (low, high, line) in _rows(RANGES, sheets[RANGES], problems):
        low, high = low or high, high or low
        if not low or not line:
            problems.append(Problem(number, "missing_key", "account_from and fs_line_key", RANGES))
        elif line not in lines:
            problems.append(Problem(number, "unknown_fs_line", line, RANGES))
        elif account_key(low) > account_key(high):
            problems.append(Problem(number, "range_invalid", f"{low}-{high}", RANGES))
        else:
            ranges.append((low, high, line))
            range_rows.append(number)
    return finish_grouping_set(
        list(groupings.values()), list(lines.values()), ranges, range_rows, problems, RANGES
    )
