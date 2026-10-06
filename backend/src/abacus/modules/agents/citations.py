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
    """What screening context may say about the rendered sheet: positions, never row data."""

    total_row: int
    last_line_row: int
    max_row: int


def _sheet(content: bytes) -> Worksheet:
    workbook = load_workbook(io.BytesIO(content), read_only=False, data_only=True)
    return cast(Worksheet, workbook.worksheets[0])


def facts(content: bytes) -> SheetFacts:
    sheet = _sheet(content)
    for row in range(2, sheet.max_row + 1):
        if cast(Cell, sheet.cell(row=row, column=2)).value == "Total":
            return SheetFacts(total_row=row, last_line_row=row - 1, max_row=sheet.max_row)
    raise ValueError("the sheet has no Total row")


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
