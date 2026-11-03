---
id: TASK-3207
title: A-05-T26 migration 0658 ebp_contributions
spec: SPEC-640
acceptance_criteria: [AC-22]
risk_zone: red
status: in-review
epic: A-05
plan_key: A-05-T26
branch: s26-a05-t26 (stacked on s26-a04-t25)
worktree: /Users/ayushkbhatia/Accrued/abacus-s26
created: 2026-11-03
updated: 2026-11-03
---

## Objective
"A second late_remittance row for the same payroll is refused and an agent cannot write a
correction event."

## Plan (red)
- Migration 0658 on 0657, expand-only:
  - `ebp_payrolls`: as imported and computed; app UPDATE revoked.
  - `ebp_late_remittances`: one row per payroll (named UNIQUE); a column grant covers the
    computed and projected columns.
  - `ebp_late_remittance_events`: insert-only (trigger). A correction or revert is a human's
    (CHECK).
- Registry and `IMMUTABLE_TABLES`.
- Test: `tests/integration/test_a05t26_ebp_contributions_migration.py`.
- Rollback: `alembic downgrade 0657`.

## Progress log
- 2026-11-03: built. Services arrive with A-05-T30 onward (EBP-04/07). Tests at the S26 end review.

## Decisions made during this task
DEC-2207.
