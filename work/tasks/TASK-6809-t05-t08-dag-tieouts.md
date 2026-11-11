---
id: TASK-6809
title: "T-05-T08: E13 part 2 workpapers/compute/dag.py and tieouts.py: dependency DAG across sheets with cycle detection, deterministic evaluation order, dirty-set propagation, formula provenance; tie-out checks foot, crossfoot, tie and off-by-n returning tally states"
spec: SPEC-651
acceptance_criteria: [AC-3.3, AC-4.2, AC-4.3]
risk_zone: amber
status: in-review
branch: s36-t05-t08
worktree: /Users/ayushkbhatia/Accrued/abacus-s36
created: 2026-11-11
updated: 2026-11-11
plan_key: T-05-T08
---

## Objective
I18 = F18+G18+H18 evaluates to (94,000), an edit recomputes only its dependents, and D+E+F+G+H+I
= J holds on every 05 Capital row.

## Plan (amber: written before the build)
1. `workpapers/compute/dag.py`: `Workbook` (cells by canonical address, sheets in tab order),
   `build_graph` (parse with `formula.parse`, edges per read address, ranges expanded), Kahn's
   order with sheet · row · column ties, `CycleError` naming the cycle, exact-Decimal `evaluate`
   (SUM, MIN, MAX, ROUND half up, IF; `div_zero` per cell and its readers), `dirty` and
   `recompute` (only dependents), provenance (`render` text and inputs).
2. `workpapers/compute/tieouts.py`: `foot`, `crossfoot`, `tie`, `off_by` → `Tally` (ties · within
   · off · missing; a missing figure is never 0).
3. Tests: `tests/unit/workpapers/test_t05t08_dag_tieouts.py` with TXP-02 row 18 and TXP-11 row 12.
4. Rollback: revert; nothing calls these yet but T-05's workbook service (T-05-T14+).

## Progress log
- `2026-11-11` — Built (S36). Tests written, not run (end pass).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3407 | Empty cell reads 0; div_zero propagates; order by sheet/row/column; tally states | no |
