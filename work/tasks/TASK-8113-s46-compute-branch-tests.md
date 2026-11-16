---
id: TASK-8113
title: S46 compute branches under the stage 2 floor (ADR-079 100% on */compute/)
spec: SPEC-000
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
branch: s46r-records
created: 2026-11-16
updated: 2026-11-16
---

## Objective
CI on #2117 (run 43853782562) failed only the `compute` coverage floor: line 99.6%, branch 98.8%
against 100%. The gaps came in with S46 rows merged without CI: A-08-T11's
`assurance/compute/reconciliation.py` (`reconcile` never called by a unit or integration test),
A-08-T12's `sampling/compute/je_selection.py` (the duplicate entry refusal) and T-07-T22's
`tax/compute/estate.py` (a missing parameter year, a zero tentative tax, the annual exclusion
outside its table, `outputs_of`).

## Acceptance
- AC-1: stage 2's `compute` coverage floor reads 100% line and 100% branch (ADR-079).

## Plan
- `backend/tests/unit/test_task8113_s46_compute_branches.py`: 8 tests, each value from the
  arithmetic or the parameter file. No source change, no floor change.

## Progress log
- 2026-11-16: 8 tests green; the three files at 100% line and branch locally. Committed on the tip
  of the follow-up stack (#2117).
