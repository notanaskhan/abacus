---
id: TASK-7605
title: W-02-T06 migration 0850 workbench_sessions_v2
plan_key: W-02-T06
spec: SPEC-653
acceptance_criteria: [AC-L3, AC-L4, AC-L6, AC-V2, AC-C4, AC-C5, AC-R4]  # the columns and kinds they need
risk_zone: amber
status: in-review
branch: w02-t06-migration
worktree: /Users/ayushkbhatia/Accrued/abacus-s40
created: 2026-11-12
updated: 2026-11-12
---

## Objective
Expand-only migration for W-02's list and context: rename and delete attribution, the list
indexes, and the wider `session_items.kind` CHECK.

## Plan
- `backend/migrations/versions/0850_workbench_sessions_v2.py` on 0842: `title_source` (`auto`,
  `manual`), `renamed_by`, `renamed_at`, `deleted_by` with pair CHECKs; GIN on `client_scope` and
  trigram GIN on `title` (both `WHERE deleted_at IS NULL`); `session_items_kind_check` widened with
  `context_added`, `context_removed`, `drill`; column UPDATE grants.
- `workbench/registry.py`: the four columns in `UPDATE_COLUMNS`.
- Test `backend/tests/integration/test_w02t06_workbench_sessions_v2_migration.py`.
- Rollback: downgrade to 0842 (drops the columns and indexes; the CHECK returns `NOT VALID` so
  rows written with the new kinds survive a rollback).

## Deviations (DEC-4605)
- The epic's owner list index already exists (0682 `workbench_sessions_owner`); not duplicated.
- `notice` was already a kind; the widening adds three.
- No column classification registry exists in the repository; the tags live on the Pydantic
  models (W-02-T02) and in the migration docstring.

## Progress log
- `2026-11-12` — Migration built (DEC-4605). Tests run at the S40 end pass.
