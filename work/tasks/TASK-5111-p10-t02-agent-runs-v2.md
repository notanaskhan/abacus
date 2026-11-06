---
id: TASK-5111
title: P-10-T02 migration 0680 agent runs v2, with status and state in sync
spec: SPEC-000  # row (P-10-T02)
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: P-10
plan_key: P-10-T02
branch: s29-p10-t02
worktree: /Users/ayushkbhatia/Accrued/abacus-s29
created: 2026-11-06
updated: 2026-11-06
---

## Objective
Additive run v2 columns on agent_runs, the sync between legacy status and canonical state, a forward-only trigger, tenant_counters.

## Plan
Migration 0680 on 0672; agents/registry.py. Expand-only. Rollback: downgrade drops every column and the trigger.

## Progress log
- 2026-11-06: built. `backend/tests/integration/test_p10t02_agent_runs_v2_migration.py` written, not run (end pass).

## Decisions made during this task
DEC-2410
