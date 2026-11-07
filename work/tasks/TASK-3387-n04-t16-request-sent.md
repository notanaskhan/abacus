---
id: TASK-3387
title: N-04-T16 payment confirmation reaches the client
spec: SPEC-000  # row (N-04-T16)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: N-04
plan_key: N-04-T16
branch: s28q-n04-binder
worktree: /Users/ayushkbhatia/Accrued/abacus-s28
created: 2026-11-07
updated: 2026-11-07
---

## Objective
DEC-2381's open binder gap.

## Plan
- `notices/sending.py` sends through `tax.api.send_confirmation`. No migration. Rollback: revert.

## Progress log
- 2026-11-07: built. `tests/integration/test_n04t21_load.py`. See DEC-2386.

## Decisions made during this task
DEC-2386
