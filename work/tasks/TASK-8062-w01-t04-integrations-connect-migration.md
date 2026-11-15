---
id: TASK-8062
title: "W-01-T04: migration 0890 integrations_connect (expand-only, firm-app backfill)"
spec: SPEC-659
acceptance_criteria: [AC-4, AC-11, AC-12, AC-13, AC-31, AC-32, AC-35]
risk_zone: red
status: in-review
branch: w01-t04-integrations-connect
worktree: /Users/ayushkbhatia/Accrued/abacus-s45
created: 2026-11-15
updated: 2026-11-15
plan_key: W-01-T04
---

## Objective
C20 v2's tables and columns, expand-only, with every live client connection given a firm-app row.

## Plan (red: written before the build)
1. `backend/migrations/versions/0890_integrations_connect.py`.
2. `integrations/registry.py`; **protected** `abacus_tools/quality/schema_check.py` (global table).
3. Regenerated tenant-isolation tests.
Rollback: downgrade removes the new tables and columns and the backfilled firm-app rows, and
restores the v1 CHECKs.

## Progress log
- `2026-11-15` — Planned at the S45 kickoff (TASK-8029).
- `2026-11-15` — Built (DEC-5047). ruff and pyright clean. Up/down/up on a copy, schema_check and
  an insert-only probe run at the end pass under the test lock.
