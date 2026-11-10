---
id: TASK-3301
title: A-05-T41 migration 0667 EBP loans, accounts and expenses (A-05 M7)
spec: SPEC-000  # row (A-05-T41)
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: A-05
plan_key: A-05-T41
branch: s28-a05-t41
worktree: /Users/ayushkbhatia/Accrued/abacus-s28
created: 2026-11-05
updated: 2026-11-05
---

## Objective
"Upgrade and downgrade pass on the seed, and SSNs in the balance and SDBA schedules are sealed like the census."

## Plan
- Migration 0667 on 0666 (expand-only), A-05 §4.2 M7, eight tenant tables.
- Registry `EBP_ACCOUNT_TABLES`, column grants; the tenant list.
- Tests: `tests/integration/test_a05t41_ebp_accounts_migration.py`.
- Rollback: the downgrade drops the eight tables.

## Progress log
- 2026-11-05: built. Tests at the S28 end review.

## Decisions made during this task
DEC-2301
