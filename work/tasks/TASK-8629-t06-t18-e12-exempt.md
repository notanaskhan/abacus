---
id: TASK-8629
title: "T-06-T18: E12 990 engine: Part IX functional allocation, program ratio, Schedule A public support"
spec: SPEC-702
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
branch: t06-t18-e12-exempt
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-18
updated: 2026-11-18
plan_key: T-06-T18
---

## Objective
Spec section: docs/plan/epics/T-06.md §3 F5 (TXP-13 c). Part IX allocation by direct charge and time study, foot and crossfoot, program ratio, Schedule A public support test (33 1/3 percent).

## Plan (amber)
1. tax/compute/exempt.py: direct, time_study (percentages sum to 100; largest remainder), part_ix (crossfoot every line; column totals; program ratio one decimal), public_support (exact one-third test by Fraction).
2. tests/unit/tax/test_t06t18_exempt.py: Lakeshore 3,210,000 + 486,000 + 318,000 = 4,014,000 at 80.0%; a time-study line crossfoots; the one-third threshold; a non-crossfooting line refused.

## Progress log
- `2026-11-18` — Built in the S50 sequential stack (DEC-5629). Partial: the 87.4% public-support golden needs the five-year Schedule A support table from the Public Support frame, which the handoff does not give line by line; the formula and threshold are tested, the figure joins with the Lakeshore slice (T-06-T22). Gates and tests run once at the S50 end pass (build first, test last).
- `2026-11-18` — Rechecked for the S50 partials round: the TXP-13 handoff (spec, README, screenshots c to c3), the blueprint §9 Lakeshore seed and the T-06 epic give public support 87.4% only as a finished figure; no frame draws the Public Support tab or the five-year Schedule A table. The golden stays open until that table exists (never invented, AGENTS.md frontend rule 5).
