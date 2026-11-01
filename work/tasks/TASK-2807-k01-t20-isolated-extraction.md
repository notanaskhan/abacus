---
id: TASK-2807
title: K-01-T20 isolated extraction for methodology sources
spec: SPEC-000  # K-01-T20 row; docs/contracts/methodology-programs.md
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: K-01
plan_key: K-01-T20
branch: s23-k01-t20
worktree: /Users/ayushkbhatia/Accrued/abacus-s23
created: 2026-11-01
updated: 2026-11-01
---

## Objective
- **[AC-1]** "A 96-page synthetic PDF yields words and boxes for every page inside the isolated
  child, and a file with SSN patterns is held with no model call."

## Plan (red)
- Files: new `kernel/pdf_pages.py` (words with boxes, page PNG, problem codes, isolated wrappers);
  evidence `extraction._reason` and `previews._png` delegate to it (behaviour unchanged);
  `methodology/extraction.py` (extract_source, pii_hold, page_image, page_words); two GET routes in
  `methodology/import_routes.py`; error codes; reviewed-fallback audit names; contract doc.
- No migration, matrix, flag or registry edit (the routes reuse `methodology.read` and
  `methodology.import_review`).
- Tests: `tests/unit/kernel/test_k01t20_pdf_pages.py` (96 pages in the child, boxes, encrypted,
  damaged, cap, PNG, range), `tests/unit/methodology/test_k01t20_extraction.py` (SSN hold, no
  gateway import or call, problem codes). Evidence's own suites cover "unchanged".
- Rollback: revert; nothing calls `extract_source` until K-01-T21.

## Progress log
- `2026-11-01` — built; ruff, pyright clean; `make regenerate` run (route introspection, client).
  Tests at the S23 end review; security review of this red diff at the end review.

## Decisions made during this task
DEC-1855.
