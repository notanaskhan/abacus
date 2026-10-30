---
id: TASK-2118
title: T-02-T07 Migration tax_returns_v1 and the status machine
spec: SPEC-502
acceptance_criteria: [AC-8]
risk_zone: amber
status: in-review
epic: T-02
plan_key: T-02-T07
branch: s16-t02-t07
created: 2026-10-29
updated: 2026-10-29
---

## Objective
Migration 0403 (expand `tax_returns`; status events; engine summaries), `tax/status.py`, and
`tax.api.apply_transition` / `record_sync_state` (T-02 §4.2).

## Plan (amber)
- `backend/migrations/versions/0403_tax_returns_v1.py` (revises 0402).
- `tax/{status,transitions,repository,registry,api}.py`; schema_check IMMUTABLE_TABLES and pins;
  error code `transition_refused`; audit actions reviewed.
- Rollback: `alembic downgrade 0402`.

## Progress log
- 2026-10-29: built (S16 block; tests run at the batch's end review). DEC-1166. The integration
  test of the migration (up/down/up, insert-only events) joins at the end review.
