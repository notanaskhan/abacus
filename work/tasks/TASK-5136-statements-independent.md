---
id: TASK-5136
title: A-06-T39 Independent tests for the statements service
spec: SPEC-000  # row (A-06-T39)
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: A-06
plan_key: A-06-T39
branch: s29-a06-t39
worktree: /Users/ayushkbhatia/Accrued/abacus-s29
created: 2026-11-06
updated: 2026-11-06
---

## Objective
Reasons refused when missing, tie-out 63 of 63 and 62 of 63 with RJE-1, out of date on a new snapshot or entry, no arithmetic on AUD-20.

## Plan
tests/unit/reporting/test_a06t39_statements_independent.py; insert-only stays in test_a06t19_statements_migration.py.

## Progress log
- 2026-11-06: built. 9 pass. Not covered: lineage citations through C4 and agent answers staying suggestions need the completion slice, now on main; add at rebase or leave partial.

## Decisions made during this task
None.
