---
id: TASK-8903
title: "K-03-T13: Migration sheets_core (workpapers)"
spec: SPEC-721
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s53-k03t13
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-22
updated: 2026-11-22
plan_key: K-03-T13
---

## Objective
sheets, sheet_columns (11 types, classification NOT NULL), sections, rows, cells with value_state, views, row links, agent_columns, previews, runs and run rows; procedures.scoped_out_by_rule; archived_guard and RLS. Acceptance: the migration goes up/down/up, a column without classification or a twelfth type is refused, an archived engagement's sheet refuses writes, and forced RLS isolates two tenants.

## Done
- Migration 1012: 11 workpapers tables, every child scoped by (tenant, engagement, work item, sheet) under one composite FK so archived_guard covers it
- sheet_columns: 11 types (SH-1 codes, agent), classification NOT NULL, live-key unique index, soft delete with person, client-visible refused on an internal sheet (trigger)
- sheet_cells value_state CHECKs (empty iff no value; suggested/adopted/edited carry the suggestion; human/adopted/edited carry the editor)
- agent_columns save needs its preview (FK + CHECK); one live run per agent column; run rows' succeeded/failed CHECKs; previews at most 3 rows
- program_procedures.scoped_out_by_rule (update grant)
- workpapers registry, schema snapshot, tenant-isolation list
- tests/integration/test_k03t13_sheets_core_migration.py (4 tests; end pass)

## Progress log
- `2026-11-22` — Built in the S53 sequential stack (DEC-5905).

## Plan (amber)
1. `1012_sheets_core.py` on 1011. 2. workpapers registry + schema snapshot + tenant list.
3. Rollback: downgrade drops 11 tables, the guard function and the program_procedures column.
