---
id: TASK-6318
title: T-04-T03 protected bundle, matrix rows, dependencies, glossary
spec: SPEC-649
acceptance_criteria: [AC-1]  # generated allow/deny tests; the agent denied every approve, override, confirm, draft-run and request
risk_zone: red
status: partial
epic: T-04
plan_key: T-04-T03
branch: s32-t04-t03
worktree: /Users/ayushkbhatia/Accrued/abacus-s32
created: 2026-11-09
updated: 2026-11-09
---

## Objective
T-04's protected bundle: the matrix rows and glossary terms. (The planned tax → workbench dependency is dropped: workbench is an edge module nothing may import, F-03-T08; TAX-08's sessions bind to a return through `agents`.)

## Plan
- `permission-matrix/tax.yaml`: return_worksheet.read, document.approve, tax_return.request_approval,
  tax_return.draft_run, k1_treatment.read/resolve/approve/override, residency.read/request_proposal/
  confirm (issue.explain already exists in review). Regenerated `_matrix.py`, `actions.gen.ts`,
  the generated security tests.
- `MODULE_DEPENDENCIES["tax"]` unchanged: workbench is an edge module (end-pass correction).
- Glossary section "tax return workspace".
- Solo rules: "the other founder's approval" drops.

## Progress log
- `2026-11-09` — Built; generated files rebuilt with the codegen modules; tests not run (end pass).
  Partial: TABLE_OWNERS rows wait for T-04's migrations (tables don't exist yet; schema_check would
  refuse owners of absent tables); ACTIVITY_KINDS labels and notification kinds wait for the rows
  that emit those events (T15 to T17).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3018 | Who holds each new action; resolve is agent task_scope (it proposes), every decision denied to the agent | no |
- `2026-11-09` — S32 end pass: gates, unit, contract, S32 integration and web suites run; fixes folded into the end-pass PR. Status partial.
