---
id: TASK-8626
title: "T-06-T15: E4 book-tax engine (M-3 requirement, Parts II-III, M-1 reference and the 1120 path, M-2 roll)"
spec: SPEC-702
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
branch: t06-t15-e4-book-tax
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-18
updated: 2026-11-18
plan_key: T-06-T15
---

## Objective
Spec section: docs/plan/epics/T-06.md §3 F2 (TXP-04, TXP-13 d). Schedule M-3 requirement (total assets of at least $10M), Parts I-III with (a)+(b)+(c)=(d), the M-1 alternative under $50M as reference, column (d) tie to Analysis of Net Income, the 1120 M-1 starting point and the M-2 roll.

## Plan (amber)
1. tax/compute/book_tax.py: m3_requirement, reconcile_m3 (row footing, Part I and Analysis ties), m1, m1_from_1120, roll_m2. Pure Decimal.
2. tests/unit/tax/test_t06t15_book_tax.py: Ridgeline 1,256,200 to 1,250,000 with one permanent (6,200), M-1 lines 5/8/9, Granite Peak M-1 line 1 2,350,000 (3,100,000 less 750,000 tax expense), M-2 off 6,200 then tie with tax-exempt interest.

## Progress log
- `2026-11-18` — Built in the S50 sequential stack (DEC-5626). Consumes T-05's M-2 cells at the screen wiring (C9 read in T-06-T28). Not run: tests at the end pass. Gates and tests run once at the S50 end pass (build first, test last).
