---
id: TASK-8443
title: "C-01-T40: rest: CLS-10 subtotal rows and the Adjustments count"
spec: SPEC-655
acceptance_criteria: [AC-21]
risk_zone: green
status: in-review
branch: s48r-cls10-gaps
worktree: /Users/ayushkbhatia/Accrued/abacus-s48
created: 2026-11-17
updated: 2026-11-17
plan_key: C-01-T40
---

## Objective
CLS-10 drew no Gross profit, Total operating expenses or Net income rows and no Adjustments count. FluxSetOut now carries code-computed subtotals and CloseSummaryOut the live AJE count.

## Plan (green)
1. closes.flux.subtotals over the set's lines, sides from the C9 tree's classification and account type (Cost of Goods Sold, Expense, other), placed after the line they follow; change_pct through workpapers' flux_change_pct.
2. CloseSummaryOut.adjustments: AJEs in C-01-T25's live set.
3. CLS-10: SubtotalRow (rules per the spec), Adjustments segment count; fixture and tests; contract DV-a/DV-b closed.

## Progress log
- `2026-11-17` — Built (S48 rest). The figures foot to the spec (124,130 → 129,740; 92,150 → 101,425; 31,455 → 27,795, (3,660), (11.6%)); interest is other expense, outside operating expenses as the spec's 101,425 requires. Gates and tests run once at the S48 end pass (build first, test last).
