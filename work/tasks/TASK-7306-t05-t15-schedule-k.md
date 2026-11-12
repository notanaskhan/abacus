---
id: TASK-7306
title: "T-05-T15: E6 tax/compute/entity/schedule_k.py: every Schedule K line by the approved structure, Σ K-1 = K, Items J, K and L, Analysis of Net Income, §199A flags, K-1 count = Item I, state K-1 amounts view"
spec: SPEC-651
acceptance_criteria: [AC-6.1, AC-6.2, AC-6.3]
risk_zone: amber
status: in-review
branch: s37-t05-t15
worktree: /Users/ayushkbhatia/Accrued/abacus-s37
created: 2026-11-12
updated: 2026-11-12
plan_key: T-05-T15
---

## Objective
Line 2 = 1,231,600, Pell Street Ventures box 2 = 400,270, Item K = 11,048,300, and Σ K-1 = K on
every line.

## Plan (amber)
- `backend/src/abacus/modules/tax/compute/entity/schedule_k.py` (PROTECTED compute package, pure):
  `schedule_k(partners, segments, lines, method, convention, liabilities, ending_capital,
  schedule_l_line_21, state_cells)`. Lines through E5's `allocate_item` (interim closing or
  proration) or by actual payments; Item J from beginning and ending percentages; Item K by ending
  profit percentage (largest remainder); Item L ties to Schedule L line 21 or reports the off
  amount; Analysis of Net Income over lines 1–11 less 12, 13a–d, 21 (never 18a–c); §199A
  statement for non-corporate partners with a trade or business line; Item I counts; state cells
  totalled, never computed.
- Test: `backend/tests/golden/tax_entity/test_t05t15_schedule_k.py` against the Ridgeline goldens.
- No migration (sheets 06 and 09 are the store, OQ-8), no route: the `federal_k1s` step and TXP-05's
  read model are T-05's service rows.
- Rollback: revert.

## Partial
- Item L's ending capital is E7's (T-05-T19, S38); E6 takes it as an input and ties it.
- The `federal_k1s` run step that writes sheet 09 and T-02's `k1_packages` Draft is T-05's step
  handlers (later rows); E6 is the engine they call.

## Progress log
- `2026-11-12` — Built (S37). A one-off run gave Pell Street Ventures box 2 = 400,270, Item K
  footing to 11,048,300 and every check true; golden tests written, run at the end pass.
