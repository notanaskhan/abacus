---
id: TASK-3303
title: A-07-T09 migration 0669 the evidence archive (A-07 M3)
spec: SPEC-000  # row (A-07-T09)
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: A-07
plan_key: A-07-T09
branch: s28-a07-t09
worktree: /Users/ayushkbhatia/Accrued/abacus-s28
created: 2026-11-05
updated: 2026-11-05
---

## Objective
"A lock decision or addition approval written by a non-human actor is refused, and documentation_completion_date for an Oct 9, 2026 release reads Dec 8, 2026."

## Plan
- Migration 0669 on 0668 (expand-only), A-07 §4.2 M3: extend 0077's `archives`; five insert-only child tables; partial index on `work_items.archive_locked_at`.
- Registry: `archives` moves out of insert-only (column UPDATE grants); children insert-only.
- Tests: A-07-T10.
- Rollback: downgrade drops the children and v2 rows, restoring 0077's shape and constraints.

## Progress log
- 2026-11-05: built. Tests at the S28 end review.

## Decisions made during this task
DEC-2303
