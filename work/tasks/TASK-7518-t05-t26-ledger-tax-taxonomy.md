---
id: TASK-7518
title: T-05-T26 ledger C9 extension (tax form-line taxonomy, mapping judgments for the tax reviewer)
plan_key: T-05-T26
spec: SPEC-000  # T-05 §4.2 M5, F3; contract C9
acceptance_criteria: [AC-1]  # Ridgeline maps 28 of 28 after Samuel approves the one judgment; an agent cannot approve it
risk_zone: red
status: in-review
branch: t05-t26-ledger-c9
worktree: /Users/ayushkbhatia/Accrued/abacus-s39
created: 2026-11-12
updated: 2026-11-12
---

## Objective
C9 mapping sets with `taxonomy_kind = tax_form_line` referencing the C21 set version; prior-year
carry-forward; number-range and description rules; mapping judgments as proposals approved by the
tax-reviewer function only (human only).

## Plan
- Migration `0842_ledger_tax_taxonomy.py` on 0841: `mapping_sets.taxonomy_kind`,
  `reference_set_version_id`, `grouping_set_version_id` nullable with a one-target CHECK, one set per
  TB per taxonomy (replaces 0079's unique), `mapping_set_edits.form_line_key` with an at-most-one
  target CHECK and a trigger matching the row's target to its set's taxonomy.
- `ledger/tax_form_mapping.py` (new): `suggest_form_lines` (prior year → range rules → description
  rules, only mappable keys; rules are firm content passed in), `unmapped_form_lines`,
  `tax_mapping_set`, `ensure_tax_mapping_set`, `record_form_line` (human edit row; 422
  `form_line_key_unknown`), `form_line_rows`. ORM columns; `mapping_set_for` reads the `fs_line`
  set only. Exported on `ledger.api`.
- `tax/entity_mapping.py` (new): the `tax_account_mapping` proposal adapter (T-05-T23's mapper,
  DEC-4406): the approver must hold `tax_mapping.approve` (new matrix action; reviewer functions,
  agent and system denied) or 403 `level_not_permitted` with nothing written; writes into the
  return's tax set pinned to the C21 version in effect. Registered in `worksheet_review.register`.
- C9 contract (`assurance/tb_mapping_contract.py`): `MappingSetSummaryOut.taxonomy_kind`,
  `reference_set_version_id`; `AccountMappingOut.form_line_key`. T-05-T24's two C9 strict xfails
  removed. Matrix regenerated; error codes regenerated.
- Tests: `tests/unit/ledger/test_t05t26_tax_taxonomy.py`; 0842 in `test_s39_migrations.py`.

## Partial
- The firm's range and description rules have no admin table yet: callers pass rules; until a
  firm records some, suggestions are prior-year only. TXP-02's mapping view over the tax set is
  T-05-T33.
- The published TY2025 form-line set is a draft behind the two-person publish (T-05-T21): the
  adapter raises `LookupError` until a version is in effect.

## Progress log
- `2026-11-12` — Built (DEC-4518). Tests run at the S39 end pass.
- `2026-11-12` — End-pass re-review: `tax/entity_mapping.py` raises `NotFound("engagement")` for an approved mapping proposal with no engagement (was a silent no-op), so an approval never looks applied when nothing was written.
