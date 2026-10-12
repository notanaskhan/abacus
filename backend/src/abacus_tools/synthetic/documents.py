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
