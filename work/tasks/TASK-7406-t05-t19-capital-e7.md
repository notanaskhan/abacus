---
id: TASK-7406
title: "T-05-T19: E7 tax/compute/entity/capital.py: tax, 704(b) and book capital roll by partner and movement, transferee succession under Reg. §1.704-1(b)(2)(iv)(l), crossfoot, Schedule M-2 lines 1-9 with the tie to Schedule L line 21, and the §743(b) placeholder fact"
spec: SPEC-651
acceptance_criteria: [AC-7.1, AC-7.2]
risk_zone: amber
status: in-review
branch: s38-t05-t19
worktree: /Users/ayushkbhatia/Accrued/abacus-s38
created: 2026-11-12
updated: 2026-11-12
plan_key: T-05-T19
---

## Objective
Each partner's capital rolled in three bases with the transfer handled correctly and the M-2 tie
shown (TXP-07; T-05 F7).

## Plan (amber)
- `backend/src/abacus/modules/tax/compute/entity/capital.py` (red, compute package): `Movements`,
  `CapitalPartner`, `Transfer`, `capital()` → rows per partner and basis, totals, transfers
  (capital at the date, transferred share half up, §743(b) placeholder), Schedule M-2 lines 1 to
  9 on the books' basis and the tie to Schedule L line 21, Item L endings, the partners whose
  §704(b) and book columns differ, checks (crossfoot, transfers net zero, line 9 is ending, ties),
  and the engine stamp.
- Tests `tests/unit/tax/test_t05t19_capital.py` on Ridgeline's figures (331,405 = 2,319,835 × 5/35
  in all three bases; off 6,200 before the fix; 124 + 2,356 + 2,015 + 155 + 1,550 = 6,200 and line
  9 = 6,866,200 after; placeholder 28,595), refusals and the stamp.
- No migration, no route. Rollback: revert.

## Partial
- E7 is the engine only: the `capital_m2` run step that writes sheet 05 and 07's cells through
  `record_value`, the `tie_out_check` activity and the TXP-07 read model are later T-05 rows
  (T-05-T27 onward). The tax CPA's review of the figures is a human step.

## Progress log
- `2026-11-12` — Built (S38). 15 unit tests pass; lint and types clean.
