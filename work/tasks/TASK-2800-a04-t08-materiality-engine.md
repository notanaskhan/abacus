---
id: TASK-2800
title: A-04-T08 materiality engine (assurance/compute/materiality.py)
spec: SPEC-620
acceptance_criteria: [AC3.1, AC3.2, AC3.3, AC3.6, AC3.8]
risk_zone: amber
status: in-review
epic: A-04
plan_key: A-04-T08
branch: s23-a04-t08
worktree: /Users/ayushkbhatia/Accrued/abacus-s23
created: 2026-11-01
updated: 2026-11-01
---

## Objective
- "16,812,400 x 1.5% gives 252,200 with PM 189,150 and CT 12,610, 3,100,000 x 5% gives 155,000 /
  116,250 / 7,750, and the final basis 16,861,000 gives 252,900 with a 700 (0.3%) difference."

## Scope
**In**: pure engine `assurance/compute/materiality.py`: thresholds, preview, benchmark rows with
ranges, prior years at rate and growth, the option set and its keys, the final-basis
reassessment, the policy check, the engine stamp. Hypothesis properties.
**Out**: reading C9 and K-02 (A-04-T12 service), versions, cards, routes (the T01 stubs stay 501).
Status note: the backlog's "partly built" refers to SPEC-300's `fieldwork/planning.compute`
(nearest-hundred above 1,000, PM/CT rounded to 100); left untouched for the live SPEC-300 routes.

## Plan
1. Tests first: `tests/unit/assurance/test_a04t08_materiality.py` (AC figures, policy refusals,
   hash by value), `tests/property/assurance/test_a04t08_materiality_properties.py`.
2. Engine on `kernel.numeric` only; add `abacus.modules.assurance.compute` to the import-linter
   compute contract (`backend/pyproject.toml`).
3. No migration, flag, matrix or registry edit. Rollback: revert.

## Progress log
- `2026-11-01` — built; engine smoke-checked against every AC figure (252,200 / 189,150 /
  12,610; 168,100 / 126,075 / 8,405; ranges 39,500-65,900 and 24,400-40,600; PY 213,400 /
  178,500; growth 18.2; final 252,900, +700, 0.3; Granite Peak 155,000 / 116,250 / 7,750).
  Tests written, run at the S23 end review.

## Decisions made during this task
DEC-1850.
