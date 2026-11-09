"""Bank statements on scans (P-11-T36; P-11 §3; SPEC-029; DEC-3126).

A scanned statement page (its OCR words name a statement and a balance) is read a second time with
Textract TABLES while the firm's `evidence.form_extraction` variant is `all`. The tables land in
`extracted_tables` and `extracted_table_cells` with every cell's box, so each transaction row
can be lit (C-01's CLS-05 statement-line regions); the statement's own fields and checks are
SPEC-029's, run on the OCR text through `statements.from_pages` with each line's box, so a scanned
Front Range Bank statement reads exactly as its digital twin. Hostile text (ADR-052): cells are
capped and kept as text; nothing here computes a balance the page does not print.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from decimal import Decimal
from typing import Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.ocr import OcrTable, OcrWord
from abacus.kernel.uow import UnitOfWork
from abacus.modules.evidence.extraction import MAX_PAGE_LINES, TextLine
from abacus.modules.evidence.statements import ParsedStatement, from_pages

EXTRACTOR_VERSION: Final = "statement-tables-1"
_STATEMENT: Final = re.compile(r"\bstatement\b", re.I)
_BALANCE: Final = re.compile(r"\b(balance|deposits?|withdrawals?)\b", re.I)
_LINE_TOLERANCE: Final = Decimal("3")
MAX_CELL_TEXT: Final = 2000  # 0666's cell text CHECK  # points: words on one printed line


def looks_like_statement(words: Sequence[OcrWord]) -> bool:
    page = " ".join(w.text for w in words)
    return bool(_STATEMENT.search(page) and _BALANCE.search(page))


def lines_of(words: Sequence[OcrWord], width_pt: float, height_pt: float) -> tuple[TextLine, ...]:
    """Words grouped into printed lines (by their tops), each with the line's box as fractions
    of the page, exactly the shape pdfplumber's lines take for a digital statement."""
    if width_pt <= 0 or height_pt <= 0:
        return ()
    rows: list[list[OcrWord]] = []
    for word in sorted(words, key=lambda w: (w.bbox[1], w.bbox[0])):
        if rows and abs(rows[-1][0].bbox[1] - word.bbox[1]) <= _LINE_TOLERANCE:
            rows[-1].append(word)
        else:
            rows.append([word])
    out: list[TextLine] = []
    for row in rows[:MAX_PAGE_LINES]:
        row.sort(key=lambda w: w.bbox[0])
        box = (
            round(max(0.0, float(min(w.bbox[0] for w in row)) / width_pt), 4),
            round(max(0.0, float(min(w.bbox[1] for w in row)) / height_pt), 4),
            round(min(1.0, float(max(w.bbox[2] for w in row)) / width_pt), 4),
            round(min(1.0, float(max(w.bbox[3] for w in row)) / height_pt), 4),
        )
        out.append(TextLine(" ".join(w.text for w in row), box))
    return tuple(out)


def statement_from_ocr(
    pages: Sequence[tuple[Sequence[OcrWord], float, float]],
) -> ParsedStatement:
    """SPEC-029's statement fields and checks on the OCR text, each line keeping its box: the
    same parser, on the same shape of input, as the statement's digital twin."""
    page_lines = [lines_of(words, w, h) for words, w, h in pages]
    texts = ["\n".join(line.text for line in lines) for lines in page_lines]
    return from_pages(texts, [[(line.text, line.box) for line in lines] for lines in page_lines])


async def record_tables(
    tx: UnitOfWork,
    *,
    tenant_id: UUID,
    evidence_version_id: UUID | None,
    inbox_file_id: UUID | None,
    ocr_run_id: UUID | None,
    page_no: int,
    tables: Sequence[OcrTable],
) -> int:
    """The page's tables and every cell with its box (insert-only); answers the cells written."""
    written = 0
    for table in tables:
        table_id = await tx.session.scalar(
            text(
                "INSERT INTO extracted_tables (tenant_id, evidence_version_id, inbox_file_id, "
                "ocr_run_id, page_no, bbox, row_count, col_count, extractor_version) VALUES (:t, "
                ":v, :inbox, :run, "
                ":page, CAST(:bbox AS numeric(10,2)[]), :rows, :cols, :ver) RETURNING id"
            ),
            {
                "t": tenant_id,
                "v": evidence_version_id,
                "inbox": inbox_file_id,
                "run": ocr_run_id,
                "page": page_no,
                "bbox": [str(b) for b in table.bbox],
                "rows": table.rows,
                "cols": table.cols,
                "ver": EXTRACTOR_VERSION,
            },
        )
        for cell in table.cells:
            await tx.session.execute(
                text(
                    "INSERT INTO extracted_table_cells (tenant_id, table_id, row_no, col_no, "
                    "text, bbox, confidence) VALUES (:t, :table, :row, :col, :text, "
                    "CAST(:bbox AS numeric(10,2)[]), :conf)"
                ),
                {
                    "t": tenant_id,
                    "table": table_id,
                    "row": cell.row,
                    "col": cell.col,
                    "text": cell.text[:MAX_CELL_TEXT],
                    "bbox": [str(b) for b in cell.bbox],
                    "conf": cell.confidence,
                },
            )
            written += 1
    return written


def rows_have_boxes(tables: Sequence[OcrTable]) -> bool:
    """Every transaction row (after the header) has at least one cell with a box."""
    for table in tables:
        boxed = {c.row for c in table.cells if any(v != 0 for v in c.bbox)}
        if any(r not in boxed for r in range(1, table.rows)):
            return False
    return True
