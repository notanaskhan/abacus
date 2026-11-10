---
id: TASK-6526
title: "P-11-T36: bank statements on scans (Textract TABLES, statement fields on OCR text)"
spec: SPEC-029
acceptance_criteria: [AC-1]  # the row's acceptance (AC-scan-twin, AC-cell-bbox)
risk_zone: amber
status: in-review
branch: s33-p11-t36
worktree: /Users/ayushkbhatia/Accrued/abacus-s33
created: 2026-11-09
updated: 2026-11-09
plan_key: P-11-T36
---

## Objective
A scanned Front Range Bank statement yields the same statement fields and checks as its digital
twin, and every transaction row has a cell bbox.

## Plan (amber)
1. `kernel/ocr.py`: `OcrCell`, `OcrTable`, `OcrPage.tables`, `normalise_tables` (TABLE → CELL →
   WORD; rows and columns capped at 2,000 and 50 so a hostile index never sizes a grid);
   Textract and FakeOcr fill tables only for `analyze_tables`.
2. `evidence/statement_tables.py`: `looks_like_statement`, `lines_of` (OCR words to printed lines
   with boxes as page fractions, the shape pdfplumber gives a digital statement),
   `statement_from_ocr`, `record_tables` (insert-only `extracted_tables` and
   `extracted_table_cells`, 0666), `rows_have_boxes`.
3. `evidence/ocr_step._read`: while `evidence.form_extraction` covers statements (`all`), a page
   whose words name a statement and a balance is read again with `analyze_tables`; a third
   `ocr_runs` row records it; the tables and cells are inserted in the same unit of work as the
   pages; the OCR extraction row now carries each line's box and the TABLES rows, so SPEC-029's
   checks and C-01's CLS-05 statement-line regions read a scan exactly as a PDF.
4. Unit tests (`tests/unit/evidence/test_p11t36_statement_tables.py`).
Rollback: revert; the tables already exist (0666) and stay empty.

## Progress log
- `2026-11-09` — Built; tests written, not run (end pass). Partial: the daily page cap is
  checked before the TABLES reads (they are counted in the 80% warning and in `ocr_runs`, not in
  the pre-check); an intake attachment's tables are read when it is filed. The digital twin in
  the test is the synthetic generator's bank statement (layout a); the Brightwater Hale Front
  Range Bank statement scan joins the golden corpus with the scenario's scanned pages.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3126 | Statement scans read TABLES behind `all`; fields come from the OCR lines | no (ADR-110) |
