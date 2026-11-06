---
id: TASK-3336
title: T-03-T07: prepare, submit, estimates, payments union and exports
spec: SPEC-000  # row (T-03-T07)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: T-03
plan_key: T-03-T07
branch: s28r-t03-t07
worktree: /Users/ayushkbhatia/Accrued/abacus-s28
created: 2026-11-06
updated: 2026-11-06
---

## Objective
Close T-03-T07's recorded partial (DEC-2243) so T-03-T15 can load through services.

## Plan
- Migration 0670: an extension's confirmation request and submission.
- `tax/extensions.py`: prepare, submit, confirmation; `tax/estimates.py`; `tax/schedule_exports.py`; C13 gate source.
- Live routes in `schedules_contract.py`; additive `POST /v1/tax/estimates` and `ExtensionPrepareIn.lines`.

## Progress log
- 2026-11-06: built. `tests/integration/test_t03t07_schedules.py` plus T-03 contract, audit, app-gate, worker and route-introspection suites pass locally. Feld foots: 79,960, 19,990 a quarter.

## Decisions made during this task
DEC-2327
