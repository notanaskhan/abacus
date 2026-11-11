---
id: TASK-6811
title: "T-05-T10: E5 part 1 tax/compute/entity/allocation.py: ownership periods and interest transfers, straight percentage by period, §706(d) interim closing or proration under Reg. §1.706-4, every split through kernel.numeric.allocate"
spec: SPEC-651
acceptance_criteria: [AC-5, AC-10]
risk_zone: amber
status: in-review
branch: s36-t05-t10
worktree: /Users/ayushkbhatia/Accrued/abacus-s36
created: 2026-11-11
updated: 2026-11-11
plan_key: T-05-T10
---

## Objective
Ridgeline allocates 628,100 per period, partner totals sum to 1,256,200, and Pell Street II LLC
receives nothing in period 1.

## Plan (amber: written before the build)
1. `tax/compute/entity/allocation.py`: `boundary` (calendar-day, semi-monthly, monthly), `segments`
   (opening interests then each transfer; interests sum to 100), `allocate_item` (interim closing
   from the closed books' segment amounts under any convention; proration by calendar days,
   calendar-day only; each segment split by `kernel.numeric.allocate` in whole dollars), stamp.
2. Tests: `tests/unit/tax/test_t05t10_allocation.py` with TXP-06 A's Ridgeline structure.
3. Rollback: revert.

## Progress log
- `2026-11-11` — Built (S36). Tests written, not run (end pass).

## Partials
- §704(c), special allocations and the Harborview waterfall are E5 part 2 (later rows).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3409 | Boundaries, method inputs, whole-dollar largest remainder | no |
