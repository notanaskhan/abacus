---
id: TASK-3346
title: N-04-T21 the notices slice loads, from the handoff's nine notices
spec: SPEC-000  # row (N-04-T21)
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: N-04
plan_key: N-04-T21
branch: s28r-n04-t21
worktree: /Users/ayushkbhatia/Accrued/abacus-s28
created: 2026-11-06
updated: 2026-11-06
---

## Objective
Make `--slice notices` actually load. DEC-2316 said export equivalence waits for that; it had never run.

## Plan
- `tests/integration/test_n04t21_load.py`; rows from `fixtures/seed/notices.ts`; a notice engagement per notice; fixes in `notices/kind.py` and `notices/intake.py`.

## Progress log
- 2026-11-06: built. `tests/integration/test_n04t21_load.py` and the slice's unit tests: 7 passed. Create notice runs in the load through the service, not the route.

## Decisions made during this task
DEC-2335
