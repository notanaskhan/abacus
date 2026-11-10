"""P-11-T36 (TASK-6526; DEC-3126): bank statements on scans.

Row acceptance: "A scanned Front Range Bank statement yields the same statement fields and checks
as its digital twin, and every transaction row has a cell bbox."
"""

from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Any
from uuid import uuid4

from abacus.kernel import ocr
from abacus.modules.evidence import ocr_step, statement_tables
from abacus.modules.evidence.extraction import extract
from abacus.modules.evidence.statement_review import read_statement
from abacus.modules.evidence.statements import ParsedStatement, Reconciliation
from abacus.modules.evidence.statements import reconcile as reconcile_lines
from abacus_tools.synthetic.documents import bank_statement_pdf, letter_pdf

PDF = "application/pdf"


def reconcile(parsed: ParsedStatement) -> Reconciliation:
    return reconcile_lines(parsed.opening, parsed.lines, parsed.closing)


LETTER = {"width_pt": Decimal(612), "height_pt": Decimal(792)}


def _scan_of(content: bytes) -> list[tuple[list[ocr.OcrWord], float, float]]:
    """The digital twin's printed lines as OCR words in page points (what Textract would read
    off a scan of the same page): each line's words spread across the line's box."""
    found = extract(content, PDF)
    pages: list[tuple[list[ocr.OcrWord], float, float]] = []
    for lines in found.page_lines:
        words: list[ocr.OcrWord] = []
        for line in lines:
            x0, top, x1, bottom = line.box
            parts = line.text.split()
            step = (x1 - x0) / max(1, len(parts))
            for n, part in enumerate(parts):
                box = (
                    Decimal(str(round((x0 + n * step) * 612, 2))),
                    Decimal(str(round(top * 792, 2))),
                    Decimal(str(round((x0 + (n + 1) * step) * 612, 2))),
                    Decimal(str(round(bottom * 792, 2))),
                )
                words.append(ocr.OcrWord(part, box, Decimal("0.98")))
        pages.append((words, 612.0, 792.0))
    return pages


def _bbox(
    left: float, top: float, width: float, height: float
) -> dict[str, Any]:  # Any: untyped JSON or YAML (a test double)
    return {"BoundingBox": {"Left": left, "Top": top, "Width": width, "Height": height}}


def _table_blocks() -> list[dict[str, Any]]:  # Any: untyped JSON or YAML (a test double)
    words = [
        ("w1", "Date"), ("w2", "Description"), ("w3", "Amount"),
        ("w4", "12/31"), ("w5", "Deposit"), ("w6", "$5,250.00"),
    ]  # fmt: skip
    blocks: list[dict[str, Any]] = [  # Any: untyped JSON or YAML (a test double)
        {"Id": i, "BlockType": "WORD", "Text": t, "Geometry": _bbox(0.1, 0.5, 0.05, 0.01)}
        for i, t in words
    ]
    cells: list[str] = []
    for n, (word_id, _t) in enumerate(words):
        row, col = divmod(n, 3)
        cell_id = f"c{n}"
        cells.append(cell_id)
        blocks.append(
            {
                "Id": cell_id,
                "BlockType": "CELL",
                "RowIndex": row + 1,
                "ColumnIndex": col + 1,
                "Confidence": 97.5,
                "Geometry": _bbox(0.1 + 0.25 * col, 0.5 + 0.02 * row, 0.24, 0.018),
                "Relationships": [{"Type": "CHILD", "Ids": [word_id]}],
            }
        )
    blocks.append(
        {
            "Id": "t1",
            "BlockType": "TABLE",
            "Geometry": _bbox(0.1, 0.5, 0.75, 0.04),
            "Relationships": [{"Type": "CHILD", "Ids": cells}],
        }
    )
    return blocks


def test_ac_a_scan_yields_the_same_statement_fields_and_checks_as_its_digital_twin() -> None:
    content = bank_statement_pdf()
    digital = read_statement(content, PDF)
    scanned = statement_tables.statement_from_ocr(_scan_of(content))
    assert digital is not None
    for field in ("account_kind", "issuer", "last4", "period_start", "period_end"):
        assert getattr(scanned, field) == getattr(digital, field), field
    assert (scanned.opening, scanned.closing) == (digital.opening, digital.closing)
    assert [(x.posted_on, x.amount, x.description) for x in scanned.lines] == [
        (x.posted_on, x.amount, x.description) for x in digital.lines
    ]
    assert reconcile(scanned) == reconcile(digital)
    assert scanned.sources is not None and digital.sources is not None
    assert set(scanned.sources) == set(digital.sources)
    # every line keeps where it was printed, as fractions of the page (CLS-05's regions)
    assert all(x.box is not None and 0 <= x.box[0] < x.box[2] <= 1 for x in scanned.lines)


def test_ac_a_statement_that_does_not_add_up_fails_the_same_check_on_a_scan() -> None:
    content = bank_statement_pdf(closing=Decimal("1.00"))
    digital = read_statement(content, PDF)
    scanned = statement_tables.statement_from_ocr(_scan_of(content))
    assert digital is not None
    assert reconcile(scanned) == reconcile(digital)
    assert not reconcile(scanned).reconciled


def test_ac_every_transaction_row_has_a_cell_bbox() -> None:
    (table,) = ocr.normalise_tables(_table_blocks(), **LETTER)
    assert (table.rows, table.cols) == (2, 3)
    assert statement_tables.rows_have_boxes([table])
    amount = next(c for c in table.cells if (c.row, c.col) == (1, 2))
    assert amount.text == "$5,250.00" and amount.confidence == Decimal("0.975")
    assert amount.bbox == (
        Decimal("367.20"),
        Decimal("411.84"),
        Decimal("514.08"),
        Decimal("426.10"),
    )
    assert ocr_step._rows(table) == (  # pyright: ignore[reportPrivateUsage]  # the grid helper
        ("Date", "Description", "Amount"),
        ("12/31", "Deposit", "$5,250.00"),
    )


def test_a_row_without_a_boxed_cell_is_reported() -> None:
    (table,) = ocr.normalise_tables(_table_blocks(), **LETTER)
    header_only = ocr.OcrTable(table.bbox, 2, 3, tuple(c for c in table.cells if c.row == 0))
    assert not statement_tables.rows_have_boxes([header_only])


def test_hostile_cell_indexes_never_size_a_grid() -> None:
    blocks = _table_blocks()
    blocks[6]["RowIndex"] = 10**9  # a cell claiming row one billion
    (table,) = ocr.normalise_tables(blocks, **LETTER)
    assert table.rows == 2 and len(table.cells) == 5


def test_fake_ocr_reads_tables_only_for_the_tables_api() -> None:
    import hashlib
    import json

    image = b"statement-page"
    fake = ocr.FakeOcr(
        {hashlib.sha256(image).hexdigest(): json.dumps({"Blocks": _table_blocks()})}
    )
    read = asyncio.run(fake.read(image, api="detect_text", **LETTER))
    tables = asyncio.run(fake.read(image, api="analyze_tables", **LETTER))
    assert read.tables == () and len(tables.tables) == 1


def test_only_statement_pages_are_read_for_tables() -> None:
    scan = _scan_of(bank_statement_pdf())[0][0]
    assert statement_tables.looks_like_statement(scan)
    letter = _scan_of(letter_pdf())[0][0]
    assert not statement_tables.looks_like_statement(letter)


def test_record_tables_writes_every_cell_with_its_box_and_no_update() -> None:
    (table,) = ocr.normalise_tables(_table_blocks(), **LETTER)
    calls: list[tuple[str, dict[str, Any]]] = []  # Any: untyped JSON or YAML (a test double)
    table_id = uuid4()

    class Session:
        async def scalar(self, sql: object, params: dict[str, Any]) -> object:  # Any: test JSON
            calls.append((str(sql), params))
            return table_id

        async def execute(self, sql: object, params: dict[str, Any]) -> None:  # Any: test JSON
            calls.append((str(sql), params))

    class Tx:
        session = Session()

    version = uuid4()
    written = asyncio.run(
        statement_tables.record_tables(
            Tx(),  # type: ignore[arg-type]  # the session is all record_tables touches
            tenant_id=uuid4(),
            evidence_version_id=version,
            inbox_file_id=None,
            ocr_run_id=uuid4(),
            page_no=1,
            tables=[table],
        )
    )
    assert written == 6
    assert all(sql.lstrip().startswith("INSERT INTO extracted_table") for sql, _ in calls)
    head = calls[0][1]
    assert (
        head["v"] == version and head["inbox"] is None and (head["rows"], head["cols"]) == (2, 3)
    )
    assert all(len(p["bbox"]) == 4 and p["table"] == table_id for _s, p in calls[1:])


def test_ac_the_front_range_bank_scan_reads_as_its_digital_twin() -> None:
    """The corpus's scanned Front Range Bank statement (P-11-T28) against the same lines printed
    as a text PDF: the same fields, lines and reconciliation."""
    import json

    from abacus_tools.synthetic.documents import positioned_pdf
    from abacus_tools.synthetic.scanned_corpus import generate

    page = next(p for p in generate() if p.key == "front_range_statement")
    blocks = json.loads(page.textract)["Blocks"]
    words = list(ocr.normalise(blocks, **LETTER))
    scanned = statement_tables.statement_from_ocr([(words, 612.0, 792.0)])
    printed = [" ".join(w.text for w in line) for line in _printed_lines(words)]
    twin = positioned_pdf([[(50.0, 740.0 - 18 * n, text) for n, text in enumerate(printed)]])
    digital = read_statement(twin, PDF)
    assert digital is not None
    assert scanned.issuer == digital.issuer
    assert (scanned.period_start, scanned.period_end) == (digital.period_start, digital.period_end)
    assert (scanned.opening, scanned.closing) == (Decimal("14200.00"), Decimal("15600.00"))
    assert (digital.opening, digital.closing) == (scanned.opening, scanned.closing)
    assert [x.amount for x in scanned.lines] == [x.amount for x in digital.lines]
    assert [x.amount for x in scanned.lines] == [Decimal("2100.00"), Decimal("-700.00")]
    assert reconcile(scanned) == reconcile(digital) and reconcile(scanned).reconciled


def _printed_lines(words: list[ocr.OcrWord]) -> list[list[ocr.OcrWord]]:
    rows: list[list[ocr.OcrWord]] = []
    for word in sorted(words, key=lambda w: (w.bbox[1], w.bbox[0])):
        if rows and abs(rows[-1][0].bbox[1] - word.bbox[1]) <= 3:
            rows[-1].append(word)
        else:
            rows.append([word])
    return rows
