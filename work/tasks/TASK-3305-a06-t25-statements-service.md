---
id: TASK-3305
title: "A-06-T25 statements service: draft, lineage, tie-out and checklist answers"
spec: SPEC-000  # row (A-06-T25)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: A-06
plan_key: A-06-T25
branch: s28-a06-t25
worktree: /Users/ayushkbhatia/Accrued/abacus-s28
created: 2026-11-05
updated: 2026-11-05
---

## Objective
"Northwind v3 ties 63 of 63 (24 + 15 + 24), v1 reports 62 of 63 with Benefits paid off 14,850 caused by RJE-1, and the checklist totals 97 + 45 + 0 = 142."

## Plan
- `reporting/compute/fs_draft.py`, `reporting/compute/tie_out.py` (pure, Decimal).
- `reporting/statements.py`: draft, reads, out-of-date computed on read, lineage through C4, tie-out, checklist answer/adopt/review via `record_value`.
- Routes live in `statements_contract.py`: read, draft, lineage, tie-out, checklist read/answer/adopt/review. Send-draft, approval and checklist import/export stay 501 (A-06-T29/T30).
- Rollback: routes return to 501; no schema.

## Progress log
- 2026-11-05: built. Tests at the S28 end review.

## Decisions made during this task
DEC-2304
