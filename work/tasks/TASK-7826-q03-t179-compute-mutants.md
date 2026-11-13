---
id: TASK-7826
title: "Q-03-T179: the sampler and materiality packages over 85% killed"
spec: SPEC-000  # row Q-03-T179
acceptance_criteria: [AC-1]  # every compute package meets 85% killed or carries approved equivalence notes
risk_zone: amber  # tests only
status: in-review
branch: lo39-q03-t179
worktree: /Users/ayushkbhatia/Accrued/abacus-lo39
created: 2026-11-13
updated: 2026-11-13
plan_key: Q-03-T179
---

## Objective
The weekly run of 2026-11-13 (43330118713) scored the row's packages (the sampler and
materiality) under 85%: materiality 69.3%, sampling stats 70.1%, canonical 77.0%, draw 83.3%,
versions 66.7% (v 88.0%).

## Plan
- `tests/unit/assurance/test_q03t179_materiality_mutants.py` (29): the stamp's inputs rebuilt
  from the canonical-input rule, every refusal's name, the rounding edges, AUD-07's figures.
- `tests/unit/sampling/test_q03t179_sampler_mutants.py` (15): the population hash's lines, the
  stream's rejection sampling against a reference, the bounds and messages, the projections'
  two decimals.

## Measured
Local mutmut 3.8.0 over the five files (tests from unit/assurance, unit/sampling and
property/sampling only, a lower bound): materiality 93.3% (432 of 463), canonical 96.6%, draw
97.9%, stats 91.0%, versions 100%. The survivors left are mostly equivalent under the shared
context (`localcontext(None)` and `rounding=None` where CONTEXT and the default differ only by
rounding mode on ties no input reaches; `sum(..., Decimal(0))` start values over Decimal terms).

## Progress log
- 2026-11-13: built and measured locally.

## Decisions made during this task
None.
