---
id: TASK-3330
title: T-03-T12 AC tests for the questionnaire service and answer effects
spec: SPEC-000  # row (T-03-T12)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: T-03
plan_key: T-03-T12
branch: s28-t03-t12
worktree: /Users/ayushkbhatia/Accrued/abacus-s28
created: 2026-11-05
updated: 2026-11-05
---

## Objective
"The suite fails against a build where the preview leaks internal_helper, an effect runs twice or a non-owner publishes a template."

## Plan
- `tests/contracts/s28/test_t03t12_questionnaire.py`.
- Concurrency (412), locks and owner-only publish with MFA join the database suite with T-03-T05's lifecycle routes.

## Progress log
- 2026-11-05: built. Tests at the S28 end review.

## Decisions made during this task
None.
