---
id: TASK-5116
title: A-05-T48 migration 0685 estimates, related parties and parties in interest
spec: SPEC-000  # row (A-05-T48)
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: A-05
plan_key: A-05-T48
branch: s29-a05-t48
worktree: /Users/ayushkbhatia/Accrued/abacus-s29
created: 2026-11-06
updated: 2026-11-06
---

## Objective
AUD-27's tables ahead of the pre-window train, with no late-remittance amount copied.

## Plan
Migration 0685; assurance/registry.py. Routes stay stubs until AUD-27's services. Rollback: downgrade.

## Progress log
- 2026-11-06: built. `backend/tests/integration/test_a05t48_estimates_rp_migration.py` written, not run (end pass).

## Decisions made during this task
DEC-2412
