---
id: TASK-6524
title: "T-04-T11: compute package modules/tax/compute/individual/ (Feld goldens)"
spec: SPEC-649
acceptance_criteria: [AC-1]  # the row's acceptance (AC-3.2, AC-6.3, AC-7.2, AC-8.2)
risk_zone: amber
status: in-review
branch: s33-t04-t11
worktree: /Users/ayushkbhatia/Accrued/abacus-s33
created: 2026-11-09
updated: 2026-11-09
plan_key: T-04-T11
---

## Objective
Every function is pure and on the Feld inputs returns 615,605, 61,580 < 98,450, 4,674,575,
141,634/96,989/69,277 and 11,279 exactly.

## Plan (amber)
1. `tax/compute/individual/`: `engine.py` (stamp, whole-dollar half-up, parameters loader),
   `forms.py` (1040 leadsheet lines, IT-201 derived lines with NY/NYC tax as imports, DEC-77),
   `k1.py` (QBI §199A limit, outside basis, state sourcing through `kernel.numeric.allocate`
   largest remainder, PTET shares half up), `residency.py` (allocation, IT-112-R lesser-of,
   IT-225 add-backs, residency rules from day counts and the main-home answer).
2. `individual/parameters/ty2025.yaml` and `ty2027.yaml` (PROTECTED, DEC-76), beside the payments
   engine's `parameters/`, so the payments file's parser is untouched.
3. `tests/unit/tax/test_t04t11_individual_compute.py`: the Feld goldens and an import check.
Rollback: revert; nothing calls it until the workspace services (T-04-T15 onward).

## Progress log
- `2026-11-09` — Built; tests written, not run (end pass). The plan's goldens directory
  (`tests/golden/tax_individual/`, N's T20) and the CPA memo (T49) are later rows.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3124 | Where the individual parameters live; the rounding of each figure | no (ADR-231) |
