---
id: TASK-7624
title: T-05-T34 schedule read models for TXP-05 and TXP-07 (tax/entity_schedules.py)
plan_key: T-05-T34
spec: SPEC-651
acceptance_criteria: [AC-F6, AC-F7]  # server totals only; Item L off 6,200 before the fix, tie after
risk_zone: amber
status: in-review
branch: t05-t34-schedule-read-models
worktree: /Users/ayushkbhatia/Accrued/abacus-s40
created: 2026-11-12
updated: 2026-11-12
---

## Objective
Serve Schedule K (federal and state), the Form 8825 breakdown, capital accounts by partner and by
movement, and the M-2 as drafted and with the fix, with tally states and Item L facts, all totals
computed by the server from the workbook cells (ADR-050).

## Plan
- `tax/entity_schedules.py` (new): `schedule_k`, `breakdown`, `capital_rows`, `capital_totals`,
  `capital_tie`, `m2_as_drafted`, `m2_with_fix`, `item_l`, `recipients`, `workbook_values`.
- `tax/workbook_contract.py`: four routes served; additive fields (capital `name`, `totals`,
  `item_l`; M-2 `lines`, `item_l`; new `WorkbookCapitalTotalsOut`, `WorkbookItemLOut`,
  `WorkbookM2LineOut`). `docs/contracts/tax-workbook.md` notes them.
- Test `backend/tests/unit/tax/test_t05t34_schedules.py`.
- Rollback: revert; the four routes answer 501 again.

## Decisions (DEC-4619)
- `with_fix` = M-2 lines 1, 2, 3, 6, 9 from the partners' capital totals (what T-05-T50 writes).
- `by_movement` returns the same partner rows plus totals; the screen pivots (no second payload).
- Only tax basis is served (`basis: tax`); GAAP and §704(b) columns arrive with their imports.

## Partial
- State view is empty until T-05-T40's `apportionment_ptet` writes sheet 06 column D, and has no
  per-partner split until `state_k1s_k3s` (T-05-T40).
- The seed's golden Ridgeline figures (off 6,200) are asserted on the synthetic cells in the unit
  test; the seeded workbook run is T-05-T65's suite.

## Progress log
- `2026-11-12` — Read models and routes built (DEC-4619). Tests at the S40 end pass.
