---
id: TASK-5112
title: P-10-T03 migration 0681 agent runtime tables
spec: SPEC-000  # row (P-10-T03)
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: P-10
plan_key: P-10-T03
branch: s29-p10-t03
worktree: /Users/ayushkbhatia/Accrued/abacus-s29
created: 2026-11-06
updated: 2026-11-06
---

## Objective
Steps, plans, questions, events, artifacts, sign-offs, feedback and engagement AI settings, with human-only decisions enforced by the database.

## Plan
Migration 0681; agents/registry.py; usage_records gains step_id, session_id, definition_id, service_line. Rollback: downgrade drops the tables and columns.

## Progress log
- 2026-11-06: built. `backend/tests/integration/test_p10t03_agent_runtime_migration.py` written, not run (end pass).

## Decisions made during this task
DEC-2411
