---
id: TASK-7517
title: T-05-T25 adjustments C8 extension (atb, tje, ttb; TJEs; tax-only accounts)
plan_key: T-05-T25
spec: SPEC-000  # T-05 §4.2 M4, F3; contract C8 (docs/contracts/adjustments.md)
acceptance_criteria: [AC-1]  # TJE-1 reclasses 6,200 to Schedule K line 18a with net zero; every layer balances
risk_zone: red
status: in-review
branch: t05-t25-adjustments-c8
worktree: /Users/ayushkbhatia/Accrued/abacus-s39
created: 2026-11-12
updated: 2026-11-12
---

## Objective
Extend C8 for tax returns: `adjusted_tb` layers `atb`, `tje`, `ttb`; TJE numbering; zero-net
reclass entries; tax-only accounts such as 4510-T; approval by a named human under the firm's tax JE
standard.

## Plan
- Migration `0841_adjustments_tax_layers.py` on 0840: `proposed_entry_lines.account_scope` (book |
  tax_only, default book, column-granted) and one trigger function on both tables: a `tje` belongs
  to a `tax_return` work item; a `tax_only` line belongs to a `tje`. Layers stay computed.
- `adjustments/entries.py`: `NewLine`/`Line.account_scope`; `check_scope` (422
  `tax_only_outside_tje`); a TJE is always `review_required` (a named human approves it, never a
  within-threshold batch); "TJE-n" already numbers per work item and kind; `adjusted_tb` for
  `atb`/`tje`/`ttb` reads the ledger's `final` and adds the work item's approved TJE lines
  (`tax_layers`: ATB = final, TJE = debit − credit per account, TTB = ATB + TJE; a tax-only account
  appears only here).
- `adjustments/contract.py`: `Layer` gains the three; `AdjustedLineOut` gains `atb`, `tje`, `ttb`,
  `account_scope`; `LineIn`/`LineOut` carry `account_scope`; the gate admits a tax firm through the
  `tax_returns` entitlement.
- `registry.py` insert column; error codes regenerated; T-05-T24's two strict xfails for C8 removed
  (they now pass).
- Tests: `tests/unit/adjustments/test_t05t25_tax_layers.py`, 0841 in
  `tests/integration/test_s39_migrations.py`.
- Rollback: the downgrade drops the triggers and the column; the book layers are unchanged.

## Partial
- The plan merges it on the Tue Apr 25 train; here in the S39 batch. Re-check alembic heads before
  merging.

## Progress log
- `2026-11-12` — Built (DEC-4517). Tests run at the S39 end pass.
