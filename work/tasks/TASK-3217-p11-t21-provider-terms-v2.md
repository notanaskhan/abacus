---
id: TASK-3217
title: P-11-T21 provider-terms register v2 (document services; Textract draft)
spec: SPEC-520
acceptance_criteria: [AC-35]
risk_zone: red
status: in-review
epic: P-11
plan_key: P-11-T21
branch: s26-p11-t21 (stacked on s26-a06-t16)
worktree: /Users/ayushkbhatia/Accrued/abacus-s26
created: 2026-11-03
updated: 2026-11-03
---

## Objective
"The Textract entry drafted and left unapproved until counsel signs"; `covering('textract', on)`
reads the register's document services beside the model routes.

## Plan (red)
- `docs/operations/provider-terms.yaml` (PROTECTED) gains `document_services`, with the Textract
  entry as a **draft**.
- The codegen validates document services:
  - textract only;
  - draft or approved;
  - opt-out evidence and `tri_basis`;
  - an approved entry also meets the model-route rules.
  Approved entries compile into `DOCUMENT_SERVICES`.
- `TermsEntry` gains `kind`, `ai_services_opt_out` and `tri_basis`. `covering()` reads both tuples.
- Test: `tests/unit/tools/test_p11t21_provider_terms_v2.py`.

## Progress log
- 2026-11-03: built. The entry stays draft until counsel signs (a human to-do). Tests at the S26
  end review.

## Decisions made during this task
DEC-2217.
