---
id: TASK-8604
title: "T-08-T05: Migration 0960 season_setup"
spec: SPEC-710
acceptance_criteria: [AC-35, AC-5, AC-3]
risk_zone: amber
status: in-review
branch: t08-t05-season-setup-migration
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-18
updated: 2026-11-18
plan_key: T-08-T05
---

## Objective
Spec section: docs/plan/epics/T-08.md §4.2 NNNN_season_setup. Seasons, manifests, cohorts, manifest rows, asks, insert-only cohort approvals and withdrawals, execution step log; human-only CHECKs and the rows-hash pin.

## Plan (amber)
1. migrations/versions/0960_season_setup.py on 0954: eight tables with forced RLS; one ready manifest per season (partial unique); approvals pin manifest_version + rows_hash + a unique grant; approvals and withdrawals human-only bound to app.actor_kind; season_row_steps insert-only, UNIQUE (row, step, attempt).
2. Triggers season_rows_frozen (no row update under an active approval) and season_withdrawal_before_start (no withdrawal after a step ran).
3. engagements/registry.py: TABLES, INSERT_ONLY, INSERT_COLUMNS, UPDATE_COLUMNS; schema_check IMMUTABLE_TABLES.
4. Rollback: downgrade drops the eight tables and four functions (expand-only, no data on main yet).

## Progress log
- `2026-11-18` — Built in the S50 sequential stack (DEC-5604). Up/down/up runs in tests/integration/test_s50_migrations.py at the end pass. Gates and tests run once at the S50 end pass (build first, test last).
