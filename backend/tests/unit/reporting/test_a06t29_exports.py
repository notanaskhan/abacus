"""A-06-T29 (TASK-5123; A-06 §3; AUD-20): deterministic workbooks with a formula guard.

Row acceptance (the exports half): "deterministic SUM and checklist XLSX with formula-injection
guard". Send-draft stays 501 until R-02-T09 (DEC-2419).
"""

from __future__ import annotations

import io
from decimal import Decimal
from uuid import uuid4

import pytest
from openpyxl import load_workbook

from abacus.kernel.safe_xlsx import Sheet, safe_text, workbook
from abacus.modules.reporting.statements import (
    ChecklistView,
    FsApprovedByManagement,
    checklist_workbook,
)


@pytest.mark.parametrize("lead", ["=", "+", "-", "@", "\t", "\r"])
def test_a_formula_lead_is_neutralised(lead: str) -> None:
    assert safe_text(f"{lead}SUM(A1)").startswith("'")


def test_plain_text_is_untouched() -> None:
    assert safe_text("Plan administrator") == "Plan administrator"


def test_same_rows_same_bytes() -> None:
    sheets = [Sheet("S", [["a", Decimal("1.50")], ["=HACK()", 2]])]
    assert workbook(sheets) == workbook(sheets)


def _view(reason: str) -> ChecklistView:
    item = {
        "section": "Investments",
        "text": "Fair value hierarchy disclosed",
        "answer": "na",
        "reason": reason,
        "note_ref": None,
        "state": "answered",
    }
    return ChecklistView(uuid4(), uuid4(), [item], 1, 142)


def test_the_checklist_keeps_a_typed_formula_as_text() -> None:
    book = load_workbook(io.BytesIO(checklist_workbook(_view('=HYPERLINK("http://x")'))))
    sheet = book.active
    assert sheet is not None
    values = [cell.value for row in sheet.iter_rows() for cell in row]
    assert not any(isinstance(v, str) and v.startswith("=") for v in values)
    assert "1 of 142" in values


def test_the_event_carries_identifiers_only() -> None:
    event = FsApprovedByManagement(
        statement_version_id=uuid4(), engagement_id=uuid4(), work_item_id=uuid4()
    )
    assert event.event_type == "fs.approved_by_management"
