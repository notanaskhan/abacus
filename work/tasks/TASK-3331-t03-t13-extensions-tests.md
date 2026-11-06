---
id: TASK-3331
title: T-03-T13 goldens and properties for extensions
spec: SPEC-000  # row (T-03-T13)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: T-03
plan_key: T-03-T13
branch: s28-t03-t13
worktree: /Users/ayushkbhatia/Accrued/abacus-s28
created: 2026-11-05
updated: 2026-11-05
---

## Objective
"Golden YAML files carry source and reviewed_by fields, pass on exact Decimal and date equality, and tallies recompute from visible rows only."

## Plan
- `tests/golden/tax/tax13_safe_harbor.yaml` (`reviewed_by` null: no CPA yet), `tests/contracts/s28/test_t03t13_extensions.py`.
- TY2027 calendar and reviewer-function cases wait on T-03-T07's estimate schedules.

## Progress log
- 2026-11-05: built. Tests at the S28 end review.

## Decisions made during this task
None.
