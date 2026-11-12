---
id: TASK-7625
title: T-05-T35 workbook cell edit endpoint (tax/cell_edit.py)
plan_key: T-05-T35
spec: SPEC-651
acceptance_criteria: [AC-F4]  # Olivia's edit checkpoints and recomputes J12, J13; Samuel's is a proposal
risk_zone: amber
status: in-review
branch: t05-t35-cell-edit
worktree: /Users/ayushkbhatia/Accrued/abacus-s40
created: 2026-11-12
updated: 2026-11-12
---

## Objective
`PUT /v1/tax-returns/{id}/workbook/cells/{address}`: preparer-only edit with expected_version,
grammar validation, bounded synchronous recompute, a named checkpoint; a reviewer's edit becomes a
proposal.

## Plan
- `tax/cell_edit.py` (new): `book_of` (cells to the E13 DAG), `apply_edit` (edited cell and
  dependents; cycle and grammar to `formula_invalid`; bound `MAX_RECOMPUTE` 500), `checkpoint_name`,
  `edit_cell` (function check via `engagements.functions_on`, version via `review.field_timeline`,
  writes via `write_cells`, audit `workbook.cell_edited`, `review.save_checkpoint`; reviewer path
  `review.raise_review_note` anchored `cell`).
- `workpapers/api.py`: export the DAG (`FormulaWorkbook`, `FormulaCellInput`, `build_formula_graph`,
  `evaluate_workbook`, `recompute_workbook`, `dirty_cells`, `canonical_address`,
  `FormulaCycleError`).
- `tax/workbook_contract.py`: the route served; `WorkbookCellOut` gains `recomputed`,
  `proposal_note_id`, `checkpoint_id` (additive). `tax/audit_targets.py`: `tax_workbook` kind.
- Test `backend/tests/unit/tax/test_t05t35_cell_edit.py`.
- Rollback: revert; the route answers 501 again.

## Decisions (DEC-4620)
- A reviewer's proposal is a review note on the cell (P-04's note rail), not a checkpoint
  proposal: `checkpoint.propose` is agent and import only. T-05-T50's proposal adapter turns these
  into one-click applies.
- `expected_version` is the cell's field version seq, not the workbook's.

## Partial
- "Approvals over changed inputs go stale" relies on review's existing stale detection over the
  workbook content hash; per-input staleness (only approvals citing the edited inputs) is T-05-T50.
- Service paths (Olivia's checkpoint, Samuel's proposal, both 409s) are asserted in T-05-T56's
  independent suite; unit tests cover the pure parts and early refusals.

## Progress log
- `2026-11-12` — Edit service and route built (DEC-4620). Tests at the S40 end pass.
