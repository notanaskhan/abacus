---
id: TASK-3381
title: A-06-T25 run record and statements workflows
spec: SPEC-000  # row (A-06-T25)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: A-06
plan_key: A-06-T25
branch: s28p-a06-t25
worktree: /Users/ayushkbhatia/Accrued/abacus-s28
created: 2026-11-06
updated: 2026-11-06
---

## Objective
DEC-2304's partials: the DET run record, FsDraftWorkflow and TieOutWorkflow.

## Plan
- `agents/det_runs.py`; `reporting/events.py`, `statements_workflow_types.py`, `statements_workflows.py`, `statements_jobs.py`; worker pins; histories and replay test. No migration.
- Rollback: revert; a run with no version is harmless.

## Progress log
- 2026-11-06: built. Replay test (4), sandbox test, load test's a25 cases. Note templates stay open: see DEC-2380.

## Decisions made during this task
DEC-2380
