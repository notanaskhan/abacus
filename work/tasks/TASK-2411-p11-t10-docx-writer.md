---
id: TASK-2411
title: P-11-T10 DOCX writer from the same DocBlocks and layout tokens
spec: SPEC-520  # AC-20; P-11 §4.4 and ADR-320 §3
acceptance_criteria: [AC-20]
risk_zone: amber
status: in-review
epic: P-11
plan_key: P-11-T10
branch: s19-p11-t10
worktree: /Users/ayushkbhatia/Accrued/abacus-s19
created: 2026-10-30
updated: 2026-10-30
---

## Objective
DOCX through python-docx from the same DocBlock model and layout tokens (headings, clauses,
tables, letterhead, watermark, page breaks), fixed core and app properties, the ZIP rebuilt with
fixed timestamps as in `evidence/render.py`.

Acceptance: "The golden letter and report fixtures produce byte-identical DOCX across runs, and
their text equals the PDF's block text."

## Plan (amber)
Files: `reporting/render/docx.py` (`write_docx`, `docx_texts`), `render/core.py`
(`render_docx`, `DocxRenderOutput`), `reporting/api.py` (re-exports),
`tests/unit/reporting/test_p11t10_docx_writer.py`, DEC-1459. No migration, flag or dependency
(python-docx is allowlisted). Rollback: revert; nothing calls it until P-11-T11's workflow.

## Progress log
- `2026-10-30` — Built on `s19-p11-t10` off main; tests run at the end review.
