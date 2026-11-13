"""Import mode for the entity workbook (T-05-T40; T-05 §2.3 steps 3, 4, 8 and 10, OQ-5; ADR-052,
ADR-050; DEC-4703). Amber. The firm's depreciation report or state apportionment schedule, as a
CSV or xlsx body, read as hostile input into the workbook as `engine_import` cells.

- **Hostile.** At most 5 MB and 2,000 data rows; xlsx opened read-only with cached values only
  (formulas are never evaluated, macros never run); every cell is text or an exact decimal; a
  value that starts with `=`, `+`, `-` or `@` and is not a number stays text (never a formula).
  Problems answer as sheet, row, column and a fixed code (`import_invalid`, 422), never a cell's
  contents; nothing is partly written.
- **Columns by header**, case and spacing ignored, from the first row: the report's own layout
  (CCH Fixed Assets' export headers and a generic sheet). Unknown columns are ignored; a missing
  required column is a problem.
- **Where.** A depreciation report fills `02` (the screen's "02 Fixed Assets") from row 2: A asset,
  B placed in service, C cost or basis, D method, E life, F current depreciation, G bonus,
  H §179; then a total row (C, F, G, H as SUM formulas). A state schedule fills `08`'s columns F
  to H from row 2 (F state, G apportionment percentage, H PTET paid); 08's A to C stay Form 8825's
  property breakdown (T-05-T34).
- **Cited.** Every cell carries a citation note naming the import (its kind, the file's SHA-256
  prefix and the source row), which SHL-09's provenance shows; the import is audited
  `workbook_import.recorded` with the file hash, kind and row count (never the contents).
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Final, Literal
from uuid import UUID, uuid4

from abacus.kernel.errors import DomainInvalid
from abacus.kernel.uow import Ref, Scope, Target, uow
from abacus.modules.identity.api import AuthContext
from abacus.modules.tax.workbook_service import WORKBOOK, CellWrite, write_cells

ImportKind = Literal["depreciation_register", "state_apportionment"]
MAX_BYTES: Final = 5 * 1024 * 1024
MAX_ROWS: Final = 2000
MAX_TEXT: Final = 200
_SPACE: Final = re.compile(r"[\s_]+")
_NUMBER: Final = re.compile(r"^\(?-?\$?[0-9][0-9,]*(\.[0-9]+)?\)?%?$")

# header aliases (normalised) → column key; required keys per kind.
_DEPRECIATION: Final[Mapping[str, tuple[str, ...]]] = {
    "asset": ("asset", "description", "asset description", "asset name"),
    "placed_in_service": ("placed in service", "in service", "date placed in service", "pis date"),
    "cost": ("cost", "basis", "cost basis", "depreciable basis"),
    "method": ("method", "depreciation method"),
    "life": ("life", "recovery period", "class life"),
    "current": ("current depreciation", "depreciation", "current year depreciation", "cy depr"),
    "bonus": ("bonus", "bonus depreciation", "special allowance"),
    "section_179": ("section 179", "179", "sec 179", "§179"),
}
_STATES: Final[Mapping[str, tuple[str, ...]]] = {
    "state": ("state", "jurisdiction"),
    "apportionment": ("apportionment", "apportionment %", "apportionment percentage", "factor"),
    "ptet": ("ptet", "ptet paid", "pass-through entity tax", "pte tax"),
}
REQUIRED: Final[Mapping[str, frozenset[str]]] = {
    "depreciation_register": frozenset({"asset", "cost", "current"}),
    "state_apportionment": frozenset({"state", "apportionment"}),
}
_DEP_COLUMNS: Final = (
    ("asset", "A", "text"),
    ("placed_in_service", "B", "date"),
    ("cost", "C", "money"),
    ("method", "D", "text"),
    ("life", "E", "number"),
    ("current", "F", "money"),
    ("bonus", "G", "money"),
    ("section_179", "H", "money"),
)
_STATE_COLUMNS: Final = (
    ("state", "F", "text"),
    ("apportionment", "G", "percent"),
    ("ptet", "H", "money"),
)
DEP_TOTAL_COLUMNS: Final = ("C", "F", "G", "H")
LABEL: Final = {
    "depreciation_register": "Depreciation report",
    "state_apportionment": "State schedule",
}


@dataclass(frozen=True)
class Problem:
    sheet: str | None
    row: int | None
    column: str | None
    code: str


class ImportInvalid(DomainInvalid):
    """The report cannot be read; `facts.problems` lists sheet, row, column and code."""

    code = "import_invalid"


def _invalid(problems: Sequence[Problem]) -> ImportInvalid:
    return ImportInvalid(
        facts={
            "problems": [
                {"sheet": p.sheet, "row": p.row, "column": p.column, "code": p.code}
                for p in problems[:100]
            ]
        }
    )


def normalise(header: object) -> str:
    return _SPACE.sub(" ", str(header or "")).strip().casefold()


def _column_name(index: int) -> str:
    name = ""
    index += 1
    while index:
        index, rem = divmod(index - 1, 26)
        name = chr(65 + rem) + name
    return name


def _rows(data: bytes) -> tuple[str, Iterator[tuple[object, ...]]]:
    """The first sheet's rows: xlsx (a zip) read-only with cached values, else CSV (UTF-8)."""
    if data[:2] == b"PK":
        from openpyxl import load_workbook

        try:
            book = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        except Exception:
            raise _invalid([Problem(None, None, None, "unreadable_workbook")]) from None
        sheet = book.worksheets[0]
        return str(sheet.title)[:40], (tuple(r) for r in sheet.iter_rows(values_only=True))
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise _invalid([Problem(None, None, None, "not_utf8")]) from None
    return "csv", (tuple(r) for r in csv.reader(io.StringIO(text)))


def _money(raw: object) -> Decimal | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, (int, float, Decimal)) and not isinstance(raw, bool):
        return Decimal(str(raw))
    text = str(raw).strip()
    if not _NUMBER.fullmatch(text):
        raise ValueError("not_a_number")
    negative = text.startswith("(") and text.endswith(")")
    cleaned = text.strip("()").replace("$", "").replace(",", "").rstrip("%")
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        raise ValueError("not_a_number") from None
    return -value if negative else value


def _date(raw: object) -> str | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, datetime):
        return raw.date().isoformat()
    if isinstance(raw, date):
        return raw.isoformat()
    text = str(raw).strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    raise ValueError("not_a_date")


def _text(raw: object) -> str | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    if len(text) > MAX_TEXT:
        raise ValueError("too_long")
    return text  # stays text in the cell store, even when it starts with "=" (never a formula)


@dataclass(frozen=True)
class Parsed:
    kind: ImportKind
    sha256: str
    rows: tuple[tuple[int, Mapping[str, Decimal | str | None]], ...]


def parse(kind: ImportKind, data: bytes) -> Parsed:
    """The report's rows by column key (module docstring); `ImportInvalid` with every problem."""
    if len(data) > MAX_BYTES:
        raise _invalid([Problem(None, None, None, "too_large")])
    if not data:
        raise _invalid([Problem(None, None, None, "empty")])
    aliases = _DEPRECIATION if kind == "depreciation_register" else _STATES
    columns = _DEP_COLUMNS if kind == "depreciation_register" else _STATE_COLUMNS
    types = {key: t for key, _c, t in columns}
    sheet, rows = _rows(data)
    try:
        header = next(rows)
    except StopIteration:
        raise _invalid([Problem(sheet, 1, None, "no_header")]) from None
    found: dict[str, int] = {}
    for index, name in enumerate(header):
        cell = normalise(name)
        for key, names in aliases.items():
            if cell in names and key not in found:
                found[key] = index
    missing = sorted(REQUIRED[kind] - set(found))
    if missing:
        raise _invalid([Problem(sheet, 1, None, f"missing_column:{m}") for m in missing])
    problems: list[Problem] = []
    out: list[tuple[int, dict[str, Decimal | str | None]]] = []
    for number, values in enumerate(rows, start=2):
        if not any(v not in (None, "") for v in values):
            continue
        if len(out) >= MAX_ROWS:
            problems.append(Problem(sheet, None, None, "too_many_rows"))
            break
        parsed: dict[str, Decimal | str | None] = {}
        for key, index in found.items():
            raw = values[index] if index < len(values) else None
            try:
                kind_of = types[key]
                if kind_of in ("money", "number", "percent"):
                    parsed[key] = _money(raw)
                elif kind_of == "date":
                    parsed[key] = _date(raw)
                else:
                    parsed[key] = _text(raw)
            except ValueError as error:
                problems.append(Problem(sheet, number, _column_name(index), str(error)))
        for key in REQUIRED[kind]:
            if parsed.get(key) in (None, ""):
                problems.append(Problem(sheet, number, _column_name(found[key]), "required"))
        pct = parsed.get("apportionment")
        if isinstance(pct, Decimal) and not Decimal(0) <= pct <= Decimal(100):
            problems.append(Problem(sheet, number, _column_name(found["apportionment"]), "range"))
        out.append((number, parsed))
    if problems:
        raise _invalid(problems)
    if not out:
        raise _invalid([Problem(sheet, None, None, "no_rows")])
    return Parsed(kind, hashlib.sha256(data).hexdigest(), tuple(out))


def writes_for(parsed: Parsed) -> list[CellWrite]:
    """The import's cells (module docstring), each with its citation note."""
    columns = _DEP_COLUMNS if parsed.kind == "depreciation_register" else _STATE_COLUMNS
    note = f"{LABEL[parsed.kind]} import {parsed.sha256[:12]}"
    out: list[CellWrite] = []
    sheet = "02" if parsed.kind == "depreciation_register" else "08"
    for n, (source_row, row) in enumerate(parsed.rows, start=2):
        for key, col, _t in columns:
            if key not in row:
                continue
            out.append(
                CellWrite(
                    f"{sheet}!{col}{n}", row[key], "engine_import",
                    citation_note=f"{note} row {source_row}",
                )
            )  # fmt: skip
    if parsed.kind == "depreciation_register":
        last = len(parsed.rows) + 1
        total_row = last + 1
        out.append(CellWrite(f"02!A{total_row}", "Total", "formula"))
        for col in DEP_TOTAL_COLUMNS:
            total = sum(
                (
                    v
                    for _r, row in parsed.rows
                    for key, c, _t in _DEP_COLUMNS
                    if c == col and isinstance(v := row.get(key), Decimal)
                ),
                Decimal(0),
            )
            formula = f"=SUM({col}2:{col}{last})"
            out.append(CellWrite(f"02!{col}{total_row}", total, "formula", formula=formula))
    return out


@dataclass(frozen=True)
class Imported:
    import_id: UUID
    kind: ImportKind
    cells: int


async def record_import(
    ctx: AuthContext, *, return_id: UUID, engagement_id: UUID, kind: ImportKind, data: bytes
) -> Imported:
    """The route authorised `workbook_import.create` on the return (a person; agent deny). The
    cells are written in one unit of work through `write_cells` (review's versions)."""
    parsed = parse(kind, data)
    writes = writes_for(parsed)
    import_id = uuid4()
    async with uow(ctx.tenant) as tx:
        written = await write_cells(
            tx, engagement_id=engagement_id, return_id=return_id, writes=writes,
            on_behalf_of_user_id=ctx.user_id,
        )  # fmt: skip
        tx.record(
            "workbook_import.recorded",
            target=Target(WORKBOOK, return_id),
            after=Ref(
                import_id=import_id,
                kind=kind,
                file_sha256=parsed.sha256,
                rows=len(parsed.rows),
                cells=written,
            ),
            scope=Scope(engagement_id=engagement_id, work_item_id=return_id),
        )
    return Imported(import_id, kind, written)


__all__ = [
    "LABEL",
    "MAX_BYTES",
    "MAX_ROWS",
    "REQUIRED",
    "ImportInvalid",
    "ImportKind",
    "Imported",
    "Parsed",
    "parse",
    "record_import",
    "writes_for",
]
