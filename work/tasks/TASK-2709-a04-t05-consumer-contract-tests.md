---
id: TASK-2709
title: A-04-T05 consumer contract tests (C3, C4, C9, methodology programs v1, C5)
spec: SPEC-620
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: A-04
plan_key: A-04-T05
branch: s22-a04-t05
worktree: /Users/ayushkbhatia/Accrued/abacus-s22
created: 2026-10-31
updated: 2026-10-31
---

## Objective
- **[AC-1]** "The five consumer suites run green in the providers' stage 2 and fail when a field
  A-04 reads is renamed or removed."

## Scope
**In**: `backend/tests/contracts/a04_planning/test_a04_consumers.py`: C3 (decision kinds, card
raising with the recommendation tag, decide/notify/analysis/reassess routes, the `workpaper`
reviewable and facts, `record_value`, suggestion appliers, sign-offs), C4 (kinds, anchor, claim,
verifier registration), C9 (Unadjusted and Final layers, named totals and groups, FS-line
subtotals, `group_by`), methodology programs v1 (steps with `prepopulates` and PBC positions,
`step_at`, materiality range), C5 (request-item, follow-up and questionnaire drafts).
**Out**: behaviour of the providers (their own suites).

## Plan
Pin field and argument sets (subset assertions) against the exported OpenAPI and the providers'
`api.py` dataclasses and signatures. Stacked on A-04-T01. Rollback: revert.

## Progress log
- `2026-10-31` — written. Found the live C3 routes are `/v1/decision-cards/{card_id}/decide`,
  `/notify`, `/analysis-requests`, `/reassess` (actions `decision.decide`, `decision.notify`,
  `decision.request_analysis`, `decision.reassess`), not the plan's `/v1/decisions/{id}/remind`;
  the A-04-T01 contracts and the T02 screen contracts were corrected to match. Tests run at the
  S22 end review.

## Decisions made during this task
None (the route correction is recorded in DEC-1757's addendum on the T01 branch).
