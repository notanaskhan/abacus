---
id: TASK-2410
title: N-02-T32 Letter composer backend (engagement_letter_versions, C11 kind, GET and PUT in Draft)
spec: SPEC-000  # the backlog row; N-02 §3.11, §4.2 and C7 §2
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
epic: N-02
plan_key: N-02-T32
branch: s19-n02-t32
worktree: /Users/ayushkbhatia/Accrued/abacus-s19
created: 2026-10-30
updated: 2026-10-30
---

## Objective
The composed engagement letter: insert-only versions, the C11 document kind `engagement_letter`
with a variables provider bound to engagement facts, and the composer's GET and PUT in Draft
only, with fee totals computed by code.

Acceptance: "Ridgeline's letter renders through C11 with the fee 18,500 computed from 6,500 and
12,000 and the engineer's fee shown but not added."

## Plan (amber)
- Migration `0560_engagement_letter_versions` (on 0550; expand-only): the versions table with a
  guard trigger (content fixed, status forward only, approval never rewritten), column grants,
  and `current_version_id`, `mode`, `envelope_id` on `engagement_letters`.
- `engagements/letters.py`: facts, fee computation, the C11 kind and providers, `composed_letter`
  and `draft_letter`; routes in `letter_contract.py` behind the new flag
  `engagements.letter_composer`; registry, model columns; `methodology.report_template_parts`;
  `RenderTicket.content_hash` (additive).
- Regenerated: `kernel/_flags.py`, `packages/api-client`, `docs/architecture/error-codes.yaml`.
- Tests: `tests/integration/test_n02t32_letter_composer.py` (run at the end review).
- Rollback: flag off; the migration's downgrade drops the table and the three columns.

## Progress log
- `2026-10-30` — Built on `s19-n02-t32` (stacked on `s19-p11-t09`; needs #883 and #884). Found
  while building: `reporting.documents` importing `evidence.api` made any consumer of
  `reporting.api` from `engagements` close an import cycle; `record_file` moved to
  `reporting/files.py` on the T09 branch. DEC-1458.
