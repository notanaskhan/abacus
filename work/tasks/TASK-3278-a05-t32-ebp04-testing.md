---
id: TASK-3278
title: A-05-T32 EBP-04 c Testing tab
spec: SPEC-000  # row (SPEC-640 F6)
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: A-05
plan_key: A-05-T32
branch: s27-a05-t32
worktree: /Users/ayushkbhatia/Accrued/abacus-s27
created: 2026-11-04
updated: 2026-11-04
---

## Objective
"Rows 8 and 15 open their EBP-03 rows, and no recalculated match exceeds 3.5% of compensation."

## Built
- Contract first: `GET /v1/audits/{wi}/ebp/contributions/test` (`TestGridOut`, 501 stub);
  `TestGridCellOut` gains defaulted `value` and `expected`, `TestGridRowOut` gains
  `linked_item_id`. Contract test in `tests/contracts/a05_ebp/test_a05t31_payrolls.py`.
- `apps/web/src/screens/EBP-04/Testing.tsx`: the 25-participant grid (compensation, deferrals,
  match; code's recalculation per cell, exception pills), "Open in Eligibility →" on rows that trace
  to an EBP-03 item, Draft 4a schedule. The Testing tab renders it.
- Fixtures: `ebp04Test()` (synthetic compensation; rows 8 and 15 exceptions) and scenario c.

## Progress log
- 2026-11-04: built; tsc and eslint clean. Tests written, run at the end pass. A failed lint in a
  chained shell command once skipped the task file and decision; they landed in a second commit.

## Decisions made during this task
DEC-2258.
