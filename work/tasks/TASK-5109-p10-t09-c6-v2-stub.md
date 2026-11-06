---
id: TASK-5109
title: P-10-T09 C6 v2 contract stub: runs, sessions, streams, usage
spec: SPEC-000  # row (P-10-T09)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: P-10
plan_key: P-10-T09
branch: s29-p10-t09
worktree: /Users/ayushkbhatia/Accrued/abacus-s29
created: 2026-11-06
updated: 2026-11-06
---

## Objective
C6 v2 as a contract: models with classification tags and 501 routes for every run v2 endpoint, consumers for P-09, W-02 and I-02 to build against.

## Plan
agents/runs_v2_contract.py, workbench/sessions_contract.py, notifications/events_contract.py, platform/usage_contract.py; docs/contracts/agent-runs.md §9; regenerate. Rollback: revert, nothing live.

## Progress log
- 2026-11-06: built. `backend/tests/contracts/c06_v2/test_c06_v2_stub.py` written, not run (end pass). Pyright clean on the touched files.

## Decisions made during this task
DEC-2408
