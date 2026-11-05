---
id: TASK-3323
title: T-03-T10 BND-03 editing states b, c and d
spec: SPEC-000  # row (T-03-T10)
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: T-03
plan_key: T-03-T10
branch: s28-t03-t10
worktree: /Users/ayushkbhatia/Accrued/abacus-s28
created: 2026-11-05
updated: 2026-11-05
---

## Objective
"BND-03 editing states b, c and d: inline edit, six-type picker, logic row, Required toggle driving the preview marker, reorder, sticky Save bar against If-Match."

## Plan
- `screens/BND-03/Editor.tsx`: inline edit, `TypePicker`, logic row, Reorder by Move up and Move down, Save bar, 412 reload.
- Scenarios b, c, d; template-mode banner in the seed.
- Rollback: read states only.

## Progress log
- 2026-11-05: built. Tests at the S28 end review.

## Decisions made during this task
DEC-2321
