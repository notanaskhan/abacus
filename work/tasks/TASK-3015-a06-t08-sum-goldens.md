---
id: TASK-3015
title: A-06-T08 SUM golden fixtures and Hypothesis properties
spec: SPEC-642
acceptance_criteria: [AC-6]
risk_zone: amber
status: in-review
epic: A-06
plan_key: A-06-T08
branch: s25-a06-t08 (stacked on s25-a06-t11)
worktree: /Users/ayushkbhatia/Accrued/abacus-s25
created: 2026-11-02
updated: 2026-11-02
---

## Objective
"backend/tests/golden/sum/ passes with exact Decimal equality, footing and idempotence properties
hold, and the case files record the reviewing CPA."

## Built
- `backend/tests/golden/sum/{northwind_py2025,northwind_illustrative,granite_peak_fy2026}.yaml`
- `backend/tests/golden/sum/test_a06t08_sum_goldens.py`; memo `docs/quality/golden-reviews/sum@1.md`.

## Progress log
- 2026-11-02: built; the figures were checked against the engine by hand (34,150 / 22,250 / 18.1 /
  13.5; 51.2; 58.8).

## Decisions made during this task
DEC-2064.
