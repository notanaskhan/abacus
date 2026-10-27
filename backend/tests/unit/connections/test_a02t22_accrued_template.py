"""A-02-T22 (TASK-1470; A-02 R-7): the Accrued trial balance template as an import format.

Acceptance: "a template that does not foot is refused unbalanced with its difference". Around
it: a footed template parses with its own account column and the Period end line, and the
template's words never name the platform (a client may upload it in the portal, DEC-01)."""

from __future__ import annotations

import io
from datetime import date
from decimal import Decimal

from openpyxl import Workbook

from abacus.modules.connections.connector import Period
from abacus.modules.connections.import_formats import FORMATS, source_format
from abacus.modules.connections.import_parse import parse_export
from abacus.modules.connections.ledger_import import check_export

START, END = date(2025, 7, 1), date(2026, 6, 30)
TEMPLATE = FORMATS["accrued_template"]


Row = tuple[str, str, float | None, float | None]


def _template(rows: list[Row], *, total: bool) -> bytes:
    book = Workbook()
    sheet = book.active
    assert sheet is not None
    sheet.append(["Trial balance template"])
    sheet.append(["Period end: 06/30/2026"])
    sheet.append([])
    sheet.append(["Account", "Account name", "Debit", "Credit"])
    for row in rows:
        sheet.append(list(row))
    if total:
        debit = sum(r[2] or 0 for r in rows)
        credit = sum(r[3] or 0 for r in rows)
        sheet.append([None, "Total", debit, credit])
    out = io.BytesIO()
    book.save(out)
    return out.getvalue()


GRANITE: list[Row] = [
    ("1000", "Cash", 2_140_000, None),
    ("1100", "Accounts receivable", 5_860_000, None),
    ("2000", "Accounts payable", None, 4_180_000),
    ("3000", "Opening equity", None, 3_820_000),
]


def test_a_footed_template_parses_with_its_codes_names_and_period() -> None:
    parsed = parse_export(_template(GRANITE, total=True), "accrued_template", START, END)
    tb = parsed.trial_balance
    assert [(line.account_code, line.account_name) for line in tb.lines] == [
        ("1000", "Cash"),
        ("1100", "Accounts receivable"),
        ("2000", "Accounts payable"),
        ("3000", "Opening equity"),
    ]
    assert tb.period_end == END
    assert tb.total_debit == tb.total_credit == Decimal("8000000.00")
    assert not parsed.totals_from_lines


def test_ac_a_template_that_does_not_foot_is_refused_unbalanced_with_its_difference() -> None:
    off: list[Row] = [*GRANITE[:-1], ("3000", "Opening equity", None, 3_818_440)]
    checked = check_export(TEMPLATE, _template(off, total=False), Period(START, END))
    assert checked.failure == "unbalanced"
    assert checked.difference == Decimal("1560.00")
    assert checked.totals_from_lines


def test_the_template_is_an_import_source_whose_words_never_name_the_platform() -> None:
    assert TEMPLATE.source == "import_accrued_template"
    assert source_format("import_accrued_template") is TEMPLATE
    assert TEMPLATE.file_type == "xlsx" and TEMPLATE.code_style == "column"
    words = " ".join((TEMPLATE.system, *TEMPLATE.steps))
    assert "Accrued" not in words
    assert TEMPLATE.steps[-1].startswith("Upload the")


def test_ed178_a_total_labelled_in_the_account_column_is_the_control_total() -> None:
    book = Workbook()
    sheet = book.active
    assert sheet is not None
    sheet.append(["Period end: 06/30/2026"])
    sheet.append(["Account", "Account name", "Debit", "Credit"])
    for row in GRANITE:
        sheet.append(list(row))
    sheet.append(["Total", None, 8_000_100, 8_000_100])  # claims 100.00 more a side
    out = io.BytesIO()
    book.save(out)
    parsed = parse_export(out.getvalue(), "accrued_template", START, END)
    assert not parsed.totals_from_lines
    assert parsed.trial_balance.declared_debit == Decimal("8000100.00")
    checked = check_export(TEMPLATE, out.getvalue(), Period(START, END))
    assert checked.failure == "control_totals_mismatch"
