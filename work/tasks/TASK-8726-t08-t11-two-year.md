---
id: TASK-8726
title: "T-08-T11: Two-year comparison compute"
spec: SPEC-710
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
branch: t08-t11-two-year
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-19
updated: 2026-11-19
plan_key: T-08-T11
---

## Objective
tax/compute/two_year.py (pure): lines over the CPA-reviewed line map from CY and PY summaries, delta and delta percent by code (one place, half up; none on a zero prior), flags against a threshold with its policy version pinned, and acceptance staleness by values hash.

## Plan (amber)
1. tax/compute/two_year.py; tests/unit/tax/test_t08t11_two_year.py.

## Progress log
- `2026-11-19` — Built; tests pass (2). Not built: the service over the engine summaries, explanation versions, reviewer acceptance rows and comparison.xlsx; Feld's 8 flagged lines need the TAX-10 seed. Gates and tests run once at the S51 end pass (build first, test last).
