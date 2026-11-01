---
id: TASK-2815
title: A-03-T17 independent AC tests for the ledger mapping work (part one)
spec: SPEC-580
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: A-03
plan_key: A-03-T17
branch: s23-a03-t17
worktree: /Users/ayushkbhatia/Accrued/abacus-s23
created: 2026-11-01
updated: 2026-11-01
---

## Objective
- **[AC-1]** "The suite passes on main and fails when any human-only CHECK, the freeze trigger,
  the unmapped guard or the stale computation is removed." Partial: the stale computation waits
  for A-03-T14.

## Plan (red, tests only)
Unit: rules order and goldens, reserved `suggested`, kernel helpers, matrix, the unmapped guard.
Integration: the human-only CHECK, both freeze triggers, forced RLS. Rollback: revert.

## Progress log
- `2026-11-01` — written; ruff clean. Run at the S23 end review. Part two (stale computation)
  joins A-03-T14. Noted: the matrix doc names a `confirmed_actor_kind` CHECK no migration adds.

## Decisions made during this task
DEC-1864.
