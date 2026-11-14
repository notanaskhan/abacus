---
id: TASK-7939
title: "T-05-T61: reconciliation to the engine of record (Schedule K, K-1 boxes, ending capital, M-2)"
plan_key: T-05-T61
spec: SPEC-651 (T-05 F11)
acceptance_criteria: [AC-F11]
risk_zone: amber
status: in-review
branch: t05-t61-reconciliation
worktree: /Users/ayushkbhatia/Accrued/abacus-s43
created: 2026-11-14
updated: 2026-11-14
---

## Objective
A seeded one-dollar difference raises one engine_diagnostic issue, and a matching import reports
zero unexplained differences.

## Plan (amber)
- `tax/entity_reconciliation.py` (new): workbook figures by code, compare, differences, issues.
- `tax/engine_import.py`: an approved entity import raises the differences after its unit of work.
- `tax/workbook_contract.py`: `GET …/reconciliation` live; rows gain `label`, `differs`; response
  gains `accrued_label` (additive). Client regenerated.
- Tests: `backend/tests/unit/tax/test_t05t61_reconciliation.py`.
- Rollback: revert; issues raised stay as issues (closable by a person).

## Partial
- The engine key layout for entity figures is Accrued's (it matches the export's Allocations
  partner refs); CCH Axcess's real layout is validated in shadow on the pilot firm (T-05 OQ-1).
- `issue_id` on each row is not filled yet (review has no read by `source_ref`); TXP-10 lists the
  issues themselves.

## Progress log
- 2026-11-14: built; tests written, not run (S43 end pass).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-4934 | compare after approval; keys; extra engine figures are differences; shadow label | no |
