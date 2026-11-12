---
id: TASK-7623
title: T-05-T33 TB and TTB read model for TXP-02 (tax/entity_tb.py)
plan_key: T-05-T33
spec: SPEC-651
acceptance_criteria: [AC-F3]  # TXP-02 tallies match golden figures; export disabled while Unmapped > 0
risk_zone: amber
status: in-review
branch: t05-t33-tb-read-model
worktree: /Users/ayushkbhatia/Accrued/abacus-s40
created: 2026-11-12
updated: 2026-11-12
---

## Objective
Serve TXP-02's trial balance, tallies and journal entries from C8's tax layers and the trial
balance's tax form-line mapping; reads only, every figure computed by code (ADR-050).

## Plan
- `tax/entity_tb.py` (new): `account_rows` (C8 `adjusted_tb` layer `ttb` + mapping), `by_line`,
  `narrowed` (balance sheet = Schedule L lines `L…`; income statement = every other mapped line;
  unmapped filter), `tallies` (UTB, ATB, TTB foots and the unmapped `check`), `trial_balance`,
  `tb_tallies`, `journal_entries`.
- `adjustments/api.py`: export `TaxLayersView` and `adjusted_tb` (already public functions).
- `tax/workbook_contract.py`: the three routes call `entity_tb` instead of answering 501.
- Test `backend/tests/unit/tax/test_t05t33_entity_tb.py`.
- Rollback: revert; the routes answer 501 again.

## Decisions (DEC-4618)
- Balance-sheet narrowing keys on the form-line key prefix `L` (Schedule L), the T-05-T26 mapping
  set's convention; no separate statement column is stored.
- The unmapped count is over the whole TB regardless of the view or filter, so the sync chip's
  export gate never depends on what the screen narrows to.
- Proposing and approving JEs stay on A-06's endpoints; the JE list here is read-only.

## Partial
- Form 8825 breakdown by property and per-tally derivation popover payloads are not built: the
  8825 property dimension is not in the mapping set yet. Carried to T-05-T43 (TXP-05 8825 popover).
- Golden-figure match runs at the S40 end pass and in T-05-T56's independent suite.

## Progress log
- `2026-11-12` — Read model and routes built (DEC-4618). Tests at the S40 end pass.
