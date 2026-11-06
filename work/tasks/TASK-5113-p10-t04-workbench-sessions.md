---
id: TASK-5113
title: P-10-T04 migration 0682 Workbench sessions
spec: SPEC-000  # row (P-10-T04)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: P-10
plan_key: P-10-T04
branch: s29-p10-t04
worktree: /Users/ayushkbhatia/Accrued/abacus-s29
created: 2026-11-06
updated: 2026-11-06
---

## Objective
Session tables in workbench: soft delete, insert-only items, schema-versioned payload.

## Plan
Migration 0682; workbench/registry.py; agent_runs.session_id FK. Rollback: downgrade.

## Progress log
- 2026-11-06: built. `backend/tests/integration/test_p10t04_workbench_sessions_migration.py` written, not run (end pass).

## Decisions made during this task
None.
