"""SPEC-029 AC-1 to AC-4 (TASK-054): every upload is scanned before it's stored; extraction reads
PDFs and spreadsheets in an isolated child, never evaluates formulas, and reports scanned,
encrypted and damaged files as unreadable."""

from __future__ import annotations

import io
import zipfile
from datetime import date
from decimal import Decimal

import pytest
from openpyxl import Workbook

from abacus.kernel.isolation import IsolationFailed, run_isolated
from abacus.kernel.scanning import EICAR
from abacus.modules.evidence.document_fields import parse_amount, parse_date
from abacus.modules.evidence.extraction import CSV, PDF, XLSX, extract, extract_isolated
from abacus.modules.evidence.uploads import UploadRefused, checked
from abacus_tools.synthetic.documents import (
    aging_schedule_xlsx,
    bank_statement_pdf,
    encrypted_pdf,
    scanned_pdf,
)

ROWS = [
    (
        "Acme Supply",
        [Decimal("1200.00"), Decimal("300.00"), Decimal(0), Decimal(0), Decimal("75.00")],
    ),
    ("Beta Tools", [Decimal("50.00"), Decimal(0), Decimal("20.00"), Decimal(0), Decimal(0)]),
]


def _crash() -> None:
    import os

    os._exit(3)  # the child dies without a result


def _hang() -> None:
    while True:
        pass


# --- AC-1: scanning ----------------------------------------------------------------------------


def test_ac1_an_upload_carrying_the_test_signature_is_refused_before_storage() -> None:
    with pytest.raises(UploadRefused):
        checked(b"%PDF-1.4\n" + EICAR)


def test_ac1_an_archive_bomb_spreadsheet_is_refused() -> None:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", b"<Types/>")
        archive.writestr("xl/workbook.xml", b"<workbook/>")
        archive.writestr("xl/bomb.xml", b"\0" * (8 * 1024 * 1024))
    with pytest.raises(UploadRefused):
        checked(out.getvalue())


def test_ac1_a_clean_file_passes_with_its_type_and_fingerprint() -> None:
    media_type, digest = checked(bank_statement_pdf())
    assert media_type == PDF
    assert len(digest) == 64


# --- AC-2: isolation ---------------------------------------------------------------------------


def test_ac2_a_child_that_crashes_is_isolation_failed() -> None:
    with pytest.raises(IsolationFailed):
        run_isolated(_crash)


def test_ac2_a_child_that_hangs_is_stopped(monkeypatch: pytest.MonkeyPatch) -> None:
    import abacus.kernel.isolation as isolation

    monkeypatch.setattr(isolation, "TIMEOUT_SECONDS", 1)
    with pytest.raises(IsolationFailed):
        run_isolated(_hang)


def test_ac2_isolated_extraction_equals_in_process_extraction() -> None:
    content = bank_statement_pdf(layout="b")
    assert extract_isolated(content, PDF) == extract(content, PDF)


def test_ac2_a_damaged_pdf_is_unreadable_not_an_error() -> None:
    found = extract(b"%PDF-1.4\nthis is not really a pdf", PDF)
    assert (found.status, found.reason) == ("unreadable", "damaged")


# --- AC-3: scanned and encrypted PDFs ----------------------------------------------------------


def test_ac3_a_scanned_pdf_is_kept_waiting_for_ocr() -> None:
    # TASK-323 amends AC-3: no text is not a client problem; the file waits for OCR (P-32).
    found = extract(scanned_pdf(pages=2), PDF)
    assert (found.status, found.reason, found.page_count) == ("not_extracted", "needs_ocr", 2)


def test_task323_pdfium_reads_text_pdfplumber_misses(monkeypatch: pytest.MonkeyPatch) -> None:
    import pdfplumber.page

    def no_text(*_args: object, **_kwargs: object) -> str:
        return ""

    monkeypatch.setattr(pdfplumber.page.Page, "extract_text", no_text)
    found = extract(bank_statement_pdf(opening=Decimal("10000.00")), PDF)
    assert found.status == "extracted"
    assert found.statement is not None and found.statement.opening == Decimal("10000.00")
    assert found.tables == ()  # PDFium reads text, not tables


def test_ac3_a_password_protected_pdf_is_unreadable_as_encrypted() -> None:
    found = extract(encrypted_pdf(), PDF)
    assert (found.status, found.reason) == ("unreadable", "encrypted")


# --- goal 3: bank statement fields, three layouts ----------------------------------------------


@pytest.mark.parametrize("layout", ["a", "b", "c"])
def test_goal3_bank_statement_fields_are_read_in_each_layout(layout: str) -> None:
    content = bank_statement_pdf(
        layout=layout,  # pyright: ignore[reportArgumentType] -- parametrised Literal
        holder="Example Company Inc",
        last4="4471",
        opening=Decimal("10000.00"),
        credits=Decimal("5250.00"),
        debits=Decimal("3125.50"),
    )
    found = extract(content, PDF)
    statement = found.statement
    assert found.status == "extracted"
    assert statement is not None
    assert statement.holder == "Example Company Inc"
    assert statement.account_last4 == "4471"
    assert statement.period_end == date(2026, 12, 31)
    assert statement.period_start == (None if layout == "c" else date(2026, 12, 1))
    assert (statement.opening, statement.credits, statement.debits, statement.closing) == (
        Decimal("10000.00"),
        Decimal("5250.00"),
        Decimal("3125.50"),
        Decimal("12124.50"),
    )


def test_goal3_a_closing_balance_that_does_not_add_up_is_read_as_printed() -> None:
    found = extract(bank_statement_pdf(closing=Decimal("99.99")), PDF)
    assert found.statement is not None
    assert found.statement.closing == Decimal("99.99")


# --- AC-4 and goal 3: spreadsheets --------------------------------------------------------------


def test_goal3_an_aging_schedule_is_read_with_its_buckets_rows_and_total() -> None:
    found = extract(aging_schedule_xlsx(ROWS), XLSX)
    aging = found.aging
    assert aging is not None
    assert aging.as_of == date(2026, 12, 31)
    assert aging.buckets == ("Current", "1-30", "31-60", "61-90", "Over 90")
    assert [r.name for r in aging.rows] == ["Acme Supply", "Beta Tools"]
    assert aging.rows[0].total == Decimal("1575.00")
    assert aging.grand_total is not None
    assert aging.grand_total[-1] == Decimal("1645.00")


def test_ac4_formulas_are_never_evaluated() -> None:
    found = extract(aging_schedule_xlsx(ROWS, formulas=True), XLSX)
    assert found.aging is not None
    assert all(row.total is None for row in found.aging.rows)  # no cached value, not computed
    assert found.aging.grand_total is not None
    assert set(found.aging.grand_total) == {None}


def test_ac4_a_formula_saved_without_its_result_reads_as_empty_not_computed() -> None:
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet["A1"] = "=1+1"
    out = io.BytesIO()
    workbook.save(out)
    found = extract(out.getvalue(), XLSX)
    assert found.status == "extracted"
    assert found.tables[0].rows == (("",),)


def test_goal3_a_windows_1252_csv_is_read() -> None:
    found = extract("Customer,Total\nCafé Ltd,12.50\n".encode("cp1252"), CSV)
    assert found.status == "extracted"
    assert found.tables[0].rows[1] == ("Café Ltd", "12.50")


def test_goal3_images_and_word_documents_are_not_extracted() -> None:
    assert extract(b"\x89PNG\r\n", "image/png").status == "not_extracted"
    legacy = extract(b"\xd0\xcf\x11\xe0", "application/x-ole-storage")
    assert (legacy.status, legacy.reason) == ("not_extracted", "legacy_format")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("(1,234.56)", Decimal("-1234.56")),
        ("$1,234.56", Decimal("1234.56")),
        ("-12.00", Decimal("-12.00")),
        ("12.3.4", None),
        ("=SUM(A1:A2)", None),
    ],
)
def test_goal3_amounts_are_read_strictly(text: str, expected: Decimal | None) -> None:
    assert parse_amount(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("December 31, 2026", date(2026, 12, 31)),
        ("Dec. 31, 2026", date(2026, 12, 31)),
        ("12/31/2026", date(2026, 12, 31)),
        ("31 December 2026", date(2026, 12, 31)),
        ("2026-12-31", date(2026, 12, 31)),
        ("31/12/2026", None),
    ],
)
def test_goal3_dates_are_read_in_us_formats(text: str, expected: date | None) -> None:
    assert parse_date(text) == expected


def test_task334_pdf_lines_keep_their_boxes_as_fractions_of_the_page() -> None:
    from abacus.modules.evidence.uploads import page_lines_of

    found = extract(bank_statement_pdf(), PDF)
    lines = found.page_lines[0]
    assert lines and lines[0].text == "First Example Bank"
    x0, top, x1, bottom = lines[0].box
    assert 0 <= x0 < x1 <= 1 and 0 <= top < bottom <= 1
    document: dict[str, object] = {
        "page_lines": [[{"text": "A", "box": [0.1, 0.2, 0.3, 0.4]}, {"text": "bad"}]]
    }
    assert page_lines_of(document) == ((("A", (0.1, 0.2, 0.3, 0.4)),),)
    assert page_lines_of({}) == ()
