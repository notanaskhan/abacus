"""Citation verification by code (ADR-066). PROTECTED. TASK-011 design §5.

A cited cell must exist in the evidence spreadsheet; a quoted text must equal the cell's text; a
cited value must equal the cell's number. Anything else is unverified (AC-15), with a reason.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import cast

from openpyxl import load_workbook
from openpyxl.cell.cell import Cell
from openpyxl.utils.cell import coordinate_from_string
from openpyxl.worksheet.worksheet import Worksheet

from abacus.modules.agents.handoff import Citation, VerifiedCitation


@dataclass(frozen=True)
class SheetFacts:
    """What code computes from the rendered trial balance for screening (ADR-050): cell positions,
    totals summed here from the line rows, whether the sheet's own Total row agrees, and the
    account names (client content: untrusted). Never rows of amounts."""

    total_row: int
    last_line_row: int
    max_row: int
    line_count: int
    total_debit: Decimal
    total_credit: Decimal
    total_row_matches: bool
    account_names: tuple[str, ...]


def _sheet(content: bytes) -> Worksheet:
    workbook = load_workbook(io.BytesIO(content), read_only=False, data_only=True)
    return cast(Worksheet, workbook.worksheets[0])


def _value(sheet: Worksheet, row: int, column: int) -> object:
    return cast(Cell, sheet.cell(row=row, column=column)).value


def _amount(sheet: Worksheet, row: int, column: int) -> Decimal:
    found = _as_decimal(_value(sheet, row, column))
    if found is None:
        raise ValueError(f"row {row} column {column} is not an amount")
    return found


def facts(content: bytes) -> SheetFacts:
    sheet = _sheet(content)
    total_row = next(
        (
            r
            for r in range(2, sheet.max_row + 1)
            if _value(sheet, r, 1) is None and _value(sheet, r, 2) == "Total"
        ),
        None,
    )
    if total_row is None:
        raise ValueError("the sheet has no Total row")
    rows = range(2, total_row)
    debit = sum((_amount(sheet, r, 3) for r in rows), Decimal(0))
    credit = sum((_amount(sheet, r, 4) for r in rows), Decimal(0))
    return SheetFacts(
        total_row=total_row,
        last_line_row=total_row - 1,
        max_row=sheet.max_row,
        line_count=len(rows),
        total_debit=debit,
        total_credit=credit,
        total_row_matches=(
            _amount(sheet, total_row, 3) == debit and _amount(sheet, total_row, 4) == credit
        ),
        account_names=tuple(str(_value(sheet, r, 2) or "") for r in rows),
    )


def _as_decimal(value: object) -> Decimal | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def verify(content: bytes, citations: list[Citation]) -> list[VerifiedCitation]:
    sheet = _sheet(content)
    verified: list[VerifiedCitation] = []
    for citation in citations:
        column, row = coordinate_from_string(citation.cell)
        reason: str | None = None
        if row > sheet.max_row or row < 1:
            reason = "cell_not_found"
        else:
            raw = cast(Cell, sheet[f"{column}{row}"]).value
            if raw is None:
                reason = "cell_not_found"
            elif citation.quote is not None and str(raw) != citation.quote:
                reason = "quote_mismatch"
            elif citation.value is not None and _as_decimal(raw) != citation.value:
                reason = "value_mismatch"
        verified.append(
            VerifiedCitation(
                cell=citation.cell,
                quote=citation.quote,
                value=None if citation.value is None else str(citation.value),
                verified=reason is None,
                reason=reason,
            )
        )
    return verified
