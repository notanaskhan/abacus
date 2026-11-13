---
id: TASK-7702
title: T-05-T40 Run step handlers part 2 (import mode, §706(d) question, failure classes)
plan_key: T-05-T40
spec: SPEC-651
acceptance_criteria: [AC-F2]  # part-2 handlers, hostile import, the §706(d) question step and failure classes
risk_zone: amber
status: in-review
branch: t05-t40-run-steps-part2
worktree: /Users/ayushkbhatia/Accrued/abacus-s41
created: 2026-11-13
updated: 2026-11-13
---

## Objective
The five part-2 steps of the entity workbook run: import mode for the firm's depreciation report
and state schedule (hostile parse into 02 and 08 as cited `engine_import` cells), the §706(d)
convention as a P-10 run question with options from code, and Needs attention with an issue when a
step has nothing to read.

## Plan (amber)
- Files: `tax/workbook_imports.py` (new: parse, cells, `record_import`), `tax/workbook_contract.py`
  (the import route answers; 413 class), `tax/run_steps.py` (five handlers, failure classes,
  issues), `tax/entity_run_plan.py` (convention question step and levels), `tax/overview.py`
  (`tax_year_of`), `agents/run_waits.py` + `agents/api.py` (`run_step_answers`, read-only).
- Migrations, matrix and flags: none (T-05-T04's `workbook_import.create`; `tax.workbook_run`).
- Tests: `backend/tests/unit/tax/test_t05t40_run_steps_part2.py`.
- Rollback: revert; the steps answer `import_required` again and the import route 501.

## Partial
- Document citations: an imported cell cites the import by note (file hash prefix and row), not a
  `document_text` citation on a stored evidence document; storing the report as evidence and
  citing its rows waits for evidence's file-to-citation path for non-PDF reports (T-05-T65 tests
  the parse; recorded for T-05-T46's freeze).
- One state: 06 D and the state K-1 shares use the first state on the schedule; multi-state
  sourcing and PTET credit splits are T-06's E9. K-3 applicability is not decided (T-05 scope).
- The run question's HOME card (options provider in C13) is T-05-T52.

## Progress log
- 2026-11-13: built; tests written, not run (S41 end pass). OpenAPI export clean.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-4703 | import mode layout, hostile parse, failure classes and issues | no |
| DEC-4704 | the convention question step and the 04 layout | no |
