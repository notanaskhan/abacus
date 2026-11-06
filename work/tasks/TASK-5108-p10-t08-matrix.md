---
id: TASK-5108
title: P-10-T08 permission-matrix bundle for runs, sessions, events and usage
spec: SPEC-000  # row (P-10-T08)
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: P-10
plan_key: P-10-T08
branch: s29-p10-t08
worktree: /Users/ayushkbhatia/Accrued/abacus-s29
created: 2026-11-06
updated: 2026-11-06
---

## Objective
The runtime's actions, with the human-only ones denied to agent, system and support.

## Plan
agents.yaml, new workbench.yaml and notifications.yaml, platform.yaml, review.yaml (issue.create task_scope). Regenerate. Rollback: revert; no route uses them yet.

## Progress log
- 2026-11-06: built. `backend/tests/security/test_p10t08_runtime_actions_never.py` written, not run (end pass); generated allow and deny tests regenerated.

## Decisions made during this task
DEC-2407
