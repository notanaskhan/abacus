---
id: TASK-344
title: "Re-read earlier PDF uploads with the current extractor so their values can point back to the page"
spec: SPEC-315
acceptance_criteria: [AC-1]
risk_zone: amber
status: done
branch: task-335-reextract
worktree: spec005
created: 2026-10-21
updated: 2026-10-21
---

## Plan
- `evidence.repository.stale_pdf_uploads` (LIST_EXEMPT, system only) and `processing.stale_pdfs`: a firm's PDF uploads and inbox files with no reading by the current `EXTRACTOR_VERSION`.
- `abacus_tools/reextract.py`: `python -m abacus_tools.reextract <tenant-id> [--dry-run] [--limit N]`. It runs the ordinary `process_upload` on each one:
  - idempotent (one extraction per version per upload);
  - audited like any extraction;
  - it never changes the evidence;
  - readers take the newest reading (TASK-333);
  - checks aren't re-run.

## Progress log
- Dev firm: a dry run found 21 PDFs. The run gave 19 extracted with line boxes and 2 `needs_ocr` (no text layer). No other dev firm had any. Example: a v1-read PDF now previews with 10 line boxes on page 1.
- Staging and production: run it per firm after deploying v3 (a dry run first).

## Definition of done
- [x] `tests/unit/evidence/test_reextract_tool.py` passes.
- [x] check-fast passes.
