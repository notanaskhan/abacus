---
id: TASK-8627
title: "T-06-T16: E8 basis and section 752 engine"
spec: SPEC-702
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
branch: t06-t16-e8-basis
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-18
updated: 2026-11-18
plan_key: T-06-T16
---

## Objective
Spec section: docs/plan/epics/T-06.md §3 F3 (TXP-08). Nonrecourse and qualified nonrecourse sharing by year-end profit percent, beginning shares from prior-year liabilities, 752(b) deemed distributions, outside versus inside basis per partner, the 743(b) placeholder pending 754.

## Plan (amber)
1. tax/compute/basis.py: liability_shares (largest remainder to whole dollars), roll (never below zero), deemed (752(a)/752(b) from the share change), partner_basis (inside = capital + 752 share; reconciled or off), s743b_placeholder.
2. tests/unit/tax/test_t06t16_basis.py: shares 220,966 / 4,198,354 / 3,314,490 / 552,415 / 2,762,075 = 11,048,300; Feld 4,428,925 + 564,050 - 316,850 = 4,676,125 with a 166,850 deemed distribution; Pell Street II 913,820 - 885,225 = 28,595 = 360,000 - 331,405.

## Progress log
- `2026-11-18` — Built in the S50 sequential stack (DEC-5627). Not run: tests at the end pass. Gates and tests run once at the S50 end pass (build first, test last).
