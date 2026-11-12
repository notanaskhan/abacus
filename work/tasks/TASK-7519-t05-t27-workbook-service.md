---
id: TASK-7519
title: T-05-T27 workbook service (cells through record_value, sheets, provenance)
plan_key: T-05-T27
spec: SPEC-000  # T-05 F4, TXP-11; tax-workbook v1; ADR-237
acceptance_criteria: [AC-1]  # 05 Capital!J12 provenance: writer, formula, inputs, citing issue; a citation to a superseded cell reads moved
risk_zone: amber
status: in-review
branch: t05-t27-workbook-service
worktree: /Users/ayushkbhatia/Accrued/abacus-s39
created: 2026-11-12
updated: 2026-11-12
---

## Objective
Engines write cells through `review.api.record_value` (formula, engine_import, tb_linked or
human); sheet projections with range paging; cell provenance; GET workbook, sheets and cells;
`register_field_owner` and the reviewable facts for the workbook.

## Plan
- `tax/workbook_service.py` (new): addresses (`05 Capital!J12` → `05!J12`), the Form 1065 sheet
  registry (`register_sheets` for other forms), `write_cells` (record_value per cell; a formula's
  text as `05!J12:f`, written back by the closed grammar; 422 `formula_invalid`, 422
  `cell_source_invalid` for anything but an engine source or a person), `project` (row/column
  order, range paging at 400, next range), `inputs_of`, `citation_state` (moved),
  `register()` (FieldOwner `tax_workbook`, TRI; reviewable facts), so SHL-09's provenance route
  reads a cell's versions, writers and citations.
- `workpapers/api.py`: exports `parse_formula`, `render_formula`, `FormulaError` (ADR-237's
  grammar; no new evaluator).
- `tax/workbook_contract.py`: `GET …/workbook`, `…/workbook/sheets/{sheet}`,
  `…/workbook/cells/{address}` served (were 501), each `workbook.read` on the return.
- Test `tests/unit/tax/test_t05t27_workbook_service.py`.

## Partial
- One live version: the run's versions ("Version 1 · Run 1") arrive with the workbook run
  (T-05-T32); the cell's author in the sheet read is formula/person until review exposes the
  latest `value_source` on `current_values`; the per-version writer is SHL-09's provenance read.
- The issues citing a cell (`issue_ids`) come from review's issue list by citation when TXP-10
  lands (T-05-T38); empty here. The cell edit (PUT) stays 501 for T-05-T34.

## Progress log
- `2026-11-12` — Built (DEC-4519). Tests run at the S39 end pass.
