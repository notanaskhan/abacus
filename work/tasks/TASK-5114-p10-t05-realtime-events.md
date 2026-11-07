---
id: TASK-5114
title: P-10-T05 migration 0683 realtime events
spec: SPEC-000  # row (P-10-T05)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: P-10
plan_key: P-10-T05
branch: s29-p10-t05
worktree: /Users/ayushkbhatia/Accrued/abacus-s29
created: 2026-11-06
updated: 2026-11-06
---

## Objective
The invalidation log GET /v1/events replays: identifiers only, kept 24 hours, sharded notify channels.

## Plan
Migration 0683; notifications/registry.py. Rollback: downgrade.

## Progress log
- 2026-11-06: built. `backend/tests/integration/test_p10t05_realtime_events_migration.py` written, not run (end pass).

## Decisions made during this task
None.
