"""Synthetic documents for upload processing (SPEC-029; TASK-054 D4). Synthetic data only.

- `bank_statement_pdf`: a text PDF in one of three layouts (labels as US banks print them),
  written by a tiny PDF writer (no dependency).
- `scanned_pdf`: a page with a drawing and no text layer, as a scanner makes.
- `encrypted_pdf`: a text PDF whose trailer asks for a password nobody has.
- `aging_schedule_xlsx`: an accounts receivable aging, optionally with formulas (no cached values)
  and a total row that doesn't add up.
"""

from __future__ import annotations

import io
from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from typing import Literal

from openpyxl import Workbook

Layout = Literal["a", "b", "c"]


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _pdf(pages: Sequence[bytes], *, encrypt: bool = False) -> bytes:
    """A minimal PDF: one Helvetica font, one content stream per page."""
    objects: list[bytes] = []
    count = len(pages)
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(count))
    font = 3 + 2 * count
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {count} >>".encode())
    for i, stream in enumerate(pages):
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {4 + 2 * i} 0 R "
            f"/Resources << /Font << /F1 {font} 0 R >> >> >>".encode()
        )
        objects.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    trailer_extra = b""
    if encrypt:
        objects.append(
            b"<< /Filter /Standard /V 1 /R 2 /P -4 /O <"
            + b"11" * 32
            + b"> /U <"
            + b"22" * 32
            + b"> >>"
        )
        trailer_extra = b" /Encrypt %d 0 R /ID [<%s> <%s>]" % (
            len(objects),
            b"33" * 16,
            b"33" * 16,
        )
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets: list[int] = []
    for number, body in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj\n" % number + body + b"\nendobj\n")
    xref = out.tell()
    out.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1))
    for offset in offsets:
        out.write(b"%010d 00000 n \n" % offset)
    out.write(
        b"trailer\n<< /Size %d /Root 1 0 R%s >>\nstartxref\n%d\n%%%%EOF\n"
        % (len(objects) + 1, trailer_extra, xref)
    )
    return out.getvalue()


def _text_page(lines: Sequence[str]) -> bytes:
    body = "".join(f"({_escape(line)}) Tj T* " for line in lines)
    return f"BT /F1 10 Tf 14 TL 50 750 Td {body}ET".encode("latin-1")


def _money(value: Decimal) -> str:
    return f"${value:,.2f}" if value >= 0 else f"(${-value:,.2f})"


def bank_statement_pdf(
    *,
    layout: Layout = "a",
    holder: str = "Example Company Inc",
    last4: str = "1234",
    start: date = date(2026, 12, 1),
    end: date = date(2026, 12, 31),
    opening: Decimal = Decimal("10000.00"),
    credits: Decimal = Decimal("5250.00"),
    debits: Decimal = Decimal("3125.50"),
    closing: Decimal | None = None,
    encrypt: bool = False,
) -> bytes:
    """`closing` defaults to opening + credits - debits; pass another to make it not add up."""
    ending = closing if closing is not None else opening + credits - debits
    if layout == "a":
        lines = [
            "First Example Bank",
            f"Account holder: {holder}",
            f"Account number: ****{last4}",
            f"Statement period: {start:%B} {start.day}, {start.year} to "
            f"{end:%B} {end.day}, {end.year}",
            f"Beginning balance {_money(opening)}",
            f"Total deposits and other credits {_money(credits)}",
            f"Total withdrawals and other debits {_money(debits)}",
            f"Ending balance {_money(ending)}",
            "Date Description Amount",
            f"{end:%m/%d} Deposit {_money(credits)}",
        ]
    elif layout == "b":
        lines = [
            "Second Example Savings",
            f"Statement for: {holder}",
            f"Account no. XXXX-XXXX-{last4}",
            f"For the period {start:%m/%d/%Y} through {end:%m/%d/%Y}",
            f"Opening balance {opening:,.2f}",
            f"Total credits {credits:,.2f}",
            f"Total debits {debits:,.2f}",
            f"Closing balance {ending:,.2f}",
        ]
    else:
        lines = [
            "Third Example Credit Union",
            f"Prepared for {holder}",
            f"Account # {last4}",
            f"Statement date: {end:%b} {end.day}, {end.year}",
            f"Previous balance {_money(opening)}",
            f"Deposits and credits {_money(credits)}",
            f"Checks and other debits {_money(debits)}",
            f"New balance {_money(ending)}",
        ]
    return _pdf([_text_page(lines)], encrypt=encrypt)


def scanned_pdf(pages: int = 1) -> bytes:
    """Pages with a drawn box and no text, as a scanner (without OCR) makes them."""
    return _pdf([b"0.5 g 50 50 500 700 re f" for _ in range(pages)])


def encrypted_pdf() -> bytes:
    return bank_statement_pdf(encrypt=True)


AGING_HEADER = ("Customer", "Current", "1-30", "31-60", "61-90", "Over 90", "Total")


def aging_schedule_xlsx(
    rows: Sequence[tuple[str, Sequence[Decimal]]],
    *,
    company: str = "Example Company Inc",
    as_of: date = date(2026, 12, 31),
    formulas: bool = False,
    total_off_by: Decimal = Decimal(0),
) -> bytes:
    """Each row: a customer and its five bucket amounts. With `formulas`, totals are written as
    formulas with no cached value (as a script, not Excel, would save them)."""
    workbook = Workbook()
    sheet = workbook.active
    if sheet is None:
        raise RuntimeError("openpyxl made a workbook without a sheet")
    sheet.title = "AR Aging"
    sheet.append([f"{company} - Accounts receivable aging"])
    sheet.append([f"As of {as_of:%B} {as_of.day}, {as_of.year}"])
    sheet.append([])
    sheet.append(list(AGING_HEADER))
    first = sheet.max_row + 1
    for name, buckets in rows:
        n = sheet.max_row + 1
        total: object = f"=SUM(B{n}:F{n})" if formulas else float(sum(buckets, Decimal(0)))
        sheet.append([name, *(float(b) for b in buckets), total])
    last = sheet.max_row
    sums = [sum((r[1][i] for r in rows), Decimal(0)) for i in range(5)]
    grand = sum(sums, Decimal(0)) + total_off_by
    if formulas:
        cols = "BCDEFG"
        sheet.append(["Total", *(f"=SUM({c}{first}:{c}{last})" for c in cols)])
    else:
        sheet.append(["Total", *(float(s) for s in sums), float(grand)])
    out = io.BytesIO()
    workbook.save(out)
    return out.getvalue()


# --- Upload reviewer cases (SPEC-030; TASK-058) -------------------------------------------------


def detailed_statement_pdf(
    *,
    holder: str = "Example Company Inc",
    last4: str = "1234",
    start: date = date(2026, 12, 1),
    end: date = date(2026, 12, 31),
    opening: Decimal = Decimal("10000.00"),
    header_lines: tuple[str, ...] = (),
    footer_lines: tuple[str, ...] = (),
    tamper_line: int | None = None,
    second_page_closing: Decimal | None = None,
    outside_period_line: bool = False,
    duplicate_check: bool = False,
) -> bytes:
    """A statement with transaction lines and running balances. `header_lines` and
    `footer_lines` add text (a watermark, a signature line, an instruction); `outside_period_line`
    dates the third line in the month before the period and `duplicate_check` reuses check 1041
    for the last payment (both editing signs that need no arithmetic); `tamper_line` makes
    that line's running balance not follow from the one before (opening, credits, debits and
    closing still agree, so code's totals check passes); `second_page_closing` adds a summary
    page stating a different closing balance."""
    moves = (
        ("Customer deposit", Decimal("2500.00")),
        ("Check 1041", Decimal("-820.00")),
        ("ACH payroll", Decimal("-1405.50")),
        ("Customer deposit", Decimal("2750.00")),
        ("Check 1041" if duplicate_check else "Wire to supplier", Decimal("-900.00")),
    )
    credits = sum((m for _, m in moves if m > 0), Decimal(0))
    debits = -sum((m for _, m in moves if m < 0), Decimal(0))
    closing = opening + credits - debits
    lines = [
        *header_lines,
        "First Example Bank",
        f"Account holder: {holder}",
        f"Account number: ****{last4}",
        f"Statement period: {start:%B} {start.day}, {start.year} to "
        f"{end:%B} {end.day}, {end.year}",
        f"Beginning balance {_money(opening)}",
        f"Total deposits and other credits {_money(credits)}",
        f"Total withdrawals and other debits {_money(debits)}",
        f"Ending balance {_money(closing)}",
        "Date Description Amount Balance",
    ]
    balance = opening
    for n, (what, amount) in enumerate(moves, start=1):
        balance += amount
        shown = balance + Decimal("500.00") if tamper_line == n else balance
        day = min(start.day + 4 * n, 28)
        month = (end.month - 2) % 12 + 1 if outside_period_line and n == 3 else end.month
        lines.append(f"{month:02d}/{day:02d} {what} {_money(amount)} {_money(shown)}")
    lines.extend(footer_lines)
    pages = [_text_page(lines)]
    if second_page_closing is not None:
        pages.append(
            _text_page(
                [
                    "Account summary",
                    f"Account number: ****{last4}",
                    f"Closing balance as of {end:%B} {end.day}, {end.year} "
                    f"{_money(second_page_closing)}",
                ]
            )
        )
    return _pdf(pages)


def invoice_pdf(
    *,
    vendor: str = "Northwind Supplies LLC",
    total: Decimal = Decimal("4210.00"),
    dated: date = date(2026, 12, 15),
) -> bytes:
    """An invoice: the wrong kind of document for a bank statement request."""
    return _pdf(
        [
            _text_page(
                [
                    "INVOICE",
                    vendor,
                    "Invoice number: INV-20931",
                    f"Invoice date: {dated:%B} {dated.day}, {dated.year}",
                    "Bill to: Example Company Inc",
                    "Description Qty Unit price Amount",
                    f"Office chairs 10 $421.00 {_money(total)}",
                    f"Amount due {_money(total)}",
                    "Payment terms: Net 30",
                ]
            )
        ]
    )


def letter_pdf(dated: date = date(2027, 1, 10)) -> bytes:
    """A cover letter: the wrong kind of document for a statement or an aging."""
    return _pdf(
        [
            _text_page(
                [
                    "Example Company Inc",
                    f"{dated:%B} {dated.day}, {dated.year}",
                    "Dear audit team,",
                    "Please find our documents for the year-end audit attached separately.",
                    "We will send the bank statements once we receive them from the bank.",
                    "Kind regards,",
                    "Rachel, Controller",
                ]
            )
        ]
    )


def receipt_pdf(dated: date = date(2026, 12, 18)) -> bytes:
    """A store receipt: the wrong kind of document for a bank statement request."""
    return _pdf(
        [
            _text_page(
                [
                    "OFFICE DEPOT STORE 2231",
                    f"{dated:%m/%d/%Y} 14:32",
                    "Printer paper 5 x $8.99 $44.95",
                    "Sales tax $3.71",
                    "TOTAL $48.66",
                    "VISA ****9921 APPROVED",
                    "Thank you for shopping with us",
                ]
            )
        ]
    )
