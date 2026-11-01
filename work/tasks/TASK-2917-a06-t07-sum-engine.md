---
id: TASK-2917
title: A-06-T07 SUM compute library (assurance/compute/sum.py)
spec: SPEC-642
acceptance_criteria: [SPEC-642 AC-6]
risk_zone: amber
status: in-review
epic: A-06
plan_key: A-06-T07
branch: s24-a06-t07 (stacked on s24-a06-t01)
worktree: /Users/ayushkbhatia/Accrued/abacus-s24
created: 2026-11-01
updated: 2026-11-01
---

## Objective

The pure SUM engine: rollover and iron curtain with the prior-year carry, the aggregate as a percent of PM and of overall, the bar's ticks, the approaching-PM rule, below-CT exclusion, two column sets, engine version and inputs hash.

## Acceptance (backlog)

The library is pure (no I/O or clock), returns 34,150 rollover and 22,250 iron curtain for the Northwind inputs and emits engine_version and inputs_hash on every result.

## Plan

- `assurance/compute/sum.py`: `Item` (ref, signed effects under both views, below-CT and prior-year flags), `Thresholds`, `evaluate` (sums of accumulated items, aggregate = the larger in absolute value, percents one decimal half up, approaching-PM at the firm's line, default 50%), `classify_below_ct`.
- Test: `tests/unit/assurance/test_a06t07_sum.py` (Northwind 34,150 / 22,250 / 18.1% / 13.5% / ticks 5.0 and 75.0; the 96,800 projection approaches PM; hashes stable).

## Progress log

- 2026-11-01: built in abacus-s24. Tests written, not run.
