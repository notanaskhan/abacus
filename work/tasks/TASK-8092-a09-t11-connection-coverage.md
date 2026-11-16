---
id: TASK-8092
title: "A-09-T11: Migration 0897_connection_coverage (connection-index change)"
spec: SPEC-658
acceptance_criteria: [AC-0]
risk_zone: red
status: in-review
branch: a09-t11-connection-coverage
worktree: /Users/ayushkbhatia/Accrued/abacus-s46
created: 2026-11-15
updated: 2026-11-15
plan_key: A-09-T11
---

## Plan (red, expand-only)
- `connection_entity_coverage` (forced RLS): connection, entity, category, live; unique per
  connection and entity.
- Backfill one row per connection with its own entity (live = status <> 'revoked'); forced RLS
  on `connections` is lifted for the copy and restored at once (the 0068 pattern).
- Partial unique `connection_coverage_one_live` (tenant, entity, category) WHERE live: a second
  live ledger for a covered subsidiary is refused; one OneWorld connection may cover five.
- Trigger `connection_coverage_sync` on connections: insert covers the own entity; a status
  change sets `live` on every row of the connection.
- `connections_one_live_ledger` stays until the post-window contract step.
- Rollback: `alembic downgrade 0896` drops the trigger, function and table.

## Built
As planned. Tests in `tests/integration/test_a09_s46_migrations.py` (end pass).

## Progress log
- `2026-11-15` — Built.
