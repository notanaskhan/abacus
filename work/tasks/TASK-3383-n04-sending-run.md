---
id: TASK-3383
title: N-04-T19 and T21 partials, the sending path run on Postgres
spec: SPEC-000  # row (N-04-T21)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: N-04
plan_key: N-04-T21
branch: s28p-n04-t19-21
worktree: /Users/ayushkbhatia/Accrued/abacus-s28
created: 2026-11-06
updated: 2026-11-06
---

## Objective
What of N-04-T19 and T21's partials can close, and the mark-sent and agency-reply gap from the S27 rebuild.

## Plan
- A Postgres test on a loaded notice; fix what it finds. No migration.
- Rollback: revert.

## Progress log
- 2026-11-06: `tests/integration/test_n04t21_load.py` (2). Three bugs fixed. See DEC-2382 for what stays open.

## Decisions made during this task
DEC-2382
