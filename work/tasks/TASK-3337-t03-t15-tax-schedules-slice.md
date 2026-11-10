---
id: TASK-3337
title: T-03-T15 Brightwater Hale organizer v6, extensions and estimates through services
spec: SPEC-000  # row (T-03-T15)
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: T-03
plan_key: T-03-T15
branch: s28r-t03-t15
worktree: /Users/ayushkbhatia/Accrued/abacus-s28
created: 2026-11-06
updated: 2026-11-06
---

## Objective
Load BND-03 and TAX-13's data through the service and import paths (`--slice tax_schedules`).

## Plan
- `brightwater_hale/tax_schedules.py`, `files/organizer_1040.csv`, loader handlers.
- Services: `extensions.flag_new_likely`, a loader-only `prepare(loader_dates=)`, `estimates.create(quarters=)`, `assign_owner(key=, form_family=)`.

## Progress log
- 2026-11-06: built. `tests/unit/synthetic/test_t03t15_tax_schedules_slice.py` and `tests/integration/test_t03t15_load.py` (loads the slice on Postgres): pass locally.

## Decisions made during this task
DEC-2371
