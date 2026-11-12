---
id: TASK-7304
title: "T-05-T17: Migration 0821 tax_entity_core (expand-only): entity_return_profiles, partners, ownership_periods, interest_transfers, allocation_structures (insert-only versions, human-only approval), allocation_rungs, allocation_results (insert-only), k1_packages.partner_id"
spec: SPEC-651
acceptance_criteria: [AC-M1]
risk_zone: amber
status: in-review
branch: s37-t05-t17
worktree: /Users/ayushkbhatia/Accrued/abacus-s37
created: 2026-11-12
updated: 2026-11-12
plan_key: T-05-T17
---

## Objective
RLS, insert-only triggers and the single-head check pass, and the migration runs dark without
touching live-path code.

## Plan (amber)
- `backend/migrations/versions/0821_tax_entity_core.py` (on 0820): seven tables per T-05 §4.2 M1,
  each with tenant, engagement and the return's work item (FK to `work_items` and `tax_returns`),
  forced RLS through `tenant_table()`, no DELETE for the app role, column-granted inserts and
  updates; `allocation_structures` and `allocation_results` insert-only by trigger; an `approved`
  structure version must be a person's own row (CHECK on the session GUCs); proration only with
  the calendar-day convention; `k1_packages.partner_id` nullable FK.
- `tax/registry.py`: TABLES, INSERT_ONLY, INSERT_COLUMNS, UPDATE_COLUMNS.
- Test: `backend/tests/integration/test_s37_migrations.py` (down to 0813 and up; privileges).
- No service, route or flag: the T-05 services that read these come in S38 (T-05-T19 onward).
- Rollback: the downgrade drops the column and the seven tables.

## Notes
- Column name `work_item_id` follows T-05 §4.2 (T-04's tables call the same key
  `tax_return_id`).
- TIN columns on `partners` are T-05-T22's (M3).

## Progress log
- `2026-11-12` — Built (S37). Ruff clean; the migration test is written, run at the end pass.
