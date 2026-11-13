---
id: TASK-7905
title: T-05-T57 Deterministic xlsx export of the entity workbook
plan_key: T-05-T57
spec: SPEC-651
acceptance_criteria: [AC-F4]  # byte-identical for identical data; live formulas; "=" client strings stay text
risk_zone: amber
status: in-review
branch: t05-t57-workbook-xlsx
worktree: /Users/ayushkbhatia/Accrued/abacus-s42
created: 2026-11-13
updated: 2026-11-13
---

## Objective
"Open in Excel" for TXP-11, TXP-02 and TXP-07: the workbook (or one sheet) as a deterministic xlsx
with live closed-grammar formulas and client text kept as text.

## Plan (amber)
- Files: `workpapers/export_xlsx.py` (new) + `workpapers/api.py` exports; `tax/workbook_export.py`
  (new); `tax/workbook_contract.py` (the 501 export route implemented);
  `audit_trail/activity_reviewed.py` (`workbook.exported`).
- No migration. Tests: `backend/tests/unit/tax/test_t05t57_workbook_xlsx.py`.
- Rollback: revert the PR (the route answers 501 again).

## Partial
- Cell styles beyond the number format (TXP-11's column widths, fills for human cells) are not
  written; the file carries values and formulas only.
- Formula cells carry no cached value: Excel computes on open; a viewer that does not compute
  shows them blank.

## Progress log
- 2026-11-13: built; tests written, not run (S42 end pass).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-4908 | generic writer, grammar-only formulas, fixed stamp, export_blocked | no (ADR-237 / P-69 cover it) |
