---
id: TASK-3263
title: T-03-T07 extensions service and routes (visible rows and counts, approve-and-request, mark filed)
spec: SPEC-643
acceptance_criteria: [AC-7]
risk_zone: amber
status: in-review
epic: T-03
plan_key: T-03-T07
branch: s27-t03-t07
worktree: /Users/ayushkbhatia/Accrued/abacus-s27
created: 2026-11-04
updated: 2026-11-04
---

## Objective
"The seed lists foot (79 + 82 = 161; 2 + 1 + 2 = 5), Samuel's single click approves three
payments and sends three confirmation requests attributed to Samuel, and no route transmits or
stores a payment instrument."

## Plan (amber)
- `tax/extensions.py`: rows grouped per visible return (walls through `work_item_facts`) with
  counts from those rows; `approve_and_request` (approve every proposed payment as the caller,
  one confirmation request per return through C5, attributed to the caller); `patch` (mark filed
  with evidence, or flag likely with a reason, against the row version).
- `schedules_contract.py`: `GET /tax/extensions`, `POST …:approve-and-request`,
  `PATCH /tax/extensions/{id}` live; `tax/api.py` imports the module so its codes are catalogued
  (and `requests/api.py` the editor's).
- Tests: `tests/unit/tax/test_t03t07_extensions.py`.
- Partial (recorded): prepare and submit-for-approval (C13 gate registration), the estimates
  routes, confirmations per installment, follow-up drafts, the Excel exports, the DF-08 payments
  union, `TaxCalendarSweep` and `ExtensionAckConsumer` (T-03-T08 covers the ack side).

## Progress log
- 2026-11-04: built.

## Decisions made during this task
DEC-2243.
