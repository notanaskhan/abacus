---
id: TASK-8055
title: "A-09-T05: migration 0889 ledger_consolidation (red, expand-only)"
spec: SPEC-658
acceptance_criteria: [AC-0, AC-1]
risk_zone: red
status: in-review
branch: a09-t05-ledger-consolidation
worktree: /Users/ayushkbhatia/Accrued/abacus-s45
created: 2026-11-15
updated: 2026-11-15
plan_key: A-09-T05
---

## Objective
The consolidation tables in `ledger` with the database enforcing X-06 (USD, 100%, three tiers),
the engagement's entities, a human finalize and a frozen structure after finalize.

## Plan (red: written before the build)
1. `backend/migrations/versions/0889_ledger_consolidation.py` (four tables, two triggers, grants).
2. `ledger/registry.py` (TABLES, INSERT_ONLY, INSERT_COLUMNS, UPDATE_COLUMNS); security codegen.
3. `tests/integration/test_a09t05_ledger_consolidation.py`.
Rollback: downgrade drops the four tables and two functions (no other table references them).

## Progress log
- `2026-11-15` — Planned at the S45 kickoff (#2010).
- `2026-11-15` — Built (DEC-5040). ruff and pyright clean. Up/down/up, schema_check (grants and
  pins) and the DB test run at the end pass under the test lock.
