---
id: TASK-8010
title: "C-01-T10: migration ledger_cas_v1 and sync tables"
spec: SPEC-655
acceptance_criteria: []
risk_zone: red
status: todo
branch: c01-t10-ledger-cas-v1
worktree: /Users/ayushkbhatia/Accrued/abacus-s44
created: 2026-11-14
updated: 2026-11-14
plan_key: C-01-T10
---

## Objective
migration ledger_cas_v1 and sync tables.

## Plan
1. [ ] Migration 0882 on 0881, expand-only: ledger_accounts (insert-only), ledger_snapshots period_kind/period, gl_entries register columns, sync_schedules, sync_runs api_calls and dataset widening, connection_meter_usage (epic §4.2 T10).
2. [ ] Registry and IMMUTABLE_TABLES entries.
Rollback: downgrade; nothing reads the columns yet.

## Progress log
- `2026-11-14` — Planned at the S44 kickoff (TASK-8000).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
