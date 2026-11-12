---
id: TASK-7614
title: I-02-T06 migration 0851 daily_briefings
plan_key: I-02-T06
spec: SPEC-654
acceptance_criteria: [AC-1]  # single head; RLS isolates two tenants; a ready row cannot be updated; no TIN or quote column
risk_zone: red
status: in-review
branch: i02-t06-daily-briefings
worktree: /Users/ayushkbhatia/Accrued/abacus-s40
created: 2026-11-12
updated: 2026-11-12
---

## Objective
`daily_briefings` (agents, expand-only) per I-02 §4.2: engagement briefings and the viewer's day
snapshot, terminal rows immutable, the retention record type `daily_briefing`.

## Plan
- `backend/migrations/versions/0851_daily_briefings.py` on 0850: the table with its CHECKs (scope
  and engagement, user rows hold no blocks or citations, engagement rows no counts, `unavailable`
  iff a reason, blocks only when ready, the reason and prompt-ref shapes), the unique day key
  (with the zero-uuid coalesce), the viewer-day index, the terminal trigger (a non-building row is
  immutable; the key never changes), forced RLS, column grants, DELETE revoked.
- `agents/registry.py`: TABLES, INSERT_COLUMNS, UPDATE_COLUMNS (the I-02-T04 registry rows).
- `evidence/retention.py` (protected) `RECORD_TYPES` += `daily_briefing`; its 90 days are content.
- Test `backend/tests/integration/test_i02t06_daily_briefings_migration.py`.
- Rollback: downgrade to 0850 drops the table and its trigger function.

## Deviations (DEC-4611)
- The 90-day default is published retention content (Q-02-T23's import), not a literal: the
  record type is registered in code, the days arrive with the defaults set.
- `capability_version` is an integer (the epic's `int`), `facts_hash` a 32-byte sha256 or null
  while building.

## Progress log
- `2026-11-12` — Migration built (DEC-4611). Tests run at the S40 end pass.
