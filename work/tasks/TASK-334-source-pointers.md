---
id: TASK-334
title: "Source pointers: hover a value to see where it was printed; click to the outlined line or cell"
spec: SPEC-315
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5]
risk_zone: amber
status: done
branch: task-334-source-highlight
worktree: spec005
created: 2026-10-21
updated: 2026-10-21
---

## Plan keys
P-11-T36, C-01-T23 (related: statement-line regions). Recorded in docs/plan/status/status-verified.csv (TASK-901).

## Plan
- **Extraction v3:** `TextLine` (text, box) per PDF page from pdfplumber's text lines.
- **Statements:** `from_pages(pages, page_lines)` keeps each line's box, and `_sources` finds the summary values' lines. These flow through review and approval.
- **Migration 0078:** `statement_transactions.box real[4]` and `statement_datasets.field_sources jsonb`, with insert grants re-issued. Rollback is the downgrade.
- **Previews:** `PreviewView.page_lines`, plus the version-level preview and page routes (`_authorised_any_version`).
- **Web:**
  - `EvidencePreview` gains a `version` source, `highlights`, `findText` and `PageImage` overlays;
  - `SourceDrawer` works without an item;
  - a new `SourceHover`, used in `StatementReview`, `ItemDetail` screening and `Workpaper` citations.

## Notes
- PDFs uploaded before v3 have no boxes, so their pointers open at the page. A backfill to re-extract them is a separate decision.

## Definition of done
- [x] `tests/unit/evidence` (177) passes.
- [x] `task334source`, spec312, spec308, spec029 and the ItemDetail/Board suites (124 web tests) pass.
- [x] check-fast passes.
