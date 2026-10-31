---
id: TASK-2214
title: T-02-T09 practice-board read models
spec: SPEC-502
acceptance_criteria: [AC-10, AC-11, AC-12, AC-13, AC-14]
risk_zone: amber
status: done
epic: T-02
plan_key: T-02-T09
branch: s17-t02-t09
created: 2026-10-30
updated: 2026-11-01
---

## Objective
Practice-board read models (T-02 §3, §4.3; TAX-01): `GET /v1/tax-returns` with filters, sort
allowlist, office grouping and search on the list envelope; summary tiles per canonical status,
open, done, extended and office totals, all wall-safe; row facts; bulk-assign through
`engagements.api`; G-01 office facts provider; C15 search projection.

Acceptance (backlog row): "Tiles foot to 79 open, 145 done and 224 total and a walled user's
tiles, totals and rows exclude walled returns."

## Plan (amber)
- `engagements/work_item_facts.py` (new): `work_item_facts`, `work_item_offices`; exported.
- `tax/board.py` (new): filters, sort, rows, summary, assign and bulk assign, office facts,
  search document.
- `tax/returns_routes.py` (new): the router moves out of `returns_contract.py`; the board's three
  routes live, the rest stubs.
- `tax/api.py`: registers the office fact and the search projection.
- No migration, matrix or flag change; generated client regenerates.
- Tests: `tests/integration/test_t02t09_practice_board.py`; the contract stub test moves the
  board's routes to live. The 79/145/224 footing is the scenario slice's (T-02-T11).
- Rollback: revert.

## Acceptance
| Check | Test |
|---|---|
| Tiles: open, done, total, extended, offices | `test_ac10_*` |
| Walled user excluded everywhere, no hidden count | `test_ac11_*` |
| Filters, search, sort allowlist | `test_ac12_*` |
| Bulk assign refuses unseen returns | `test_ac13_*` |
| Client principal 404 | `test_inv4_*` |

## Progress log
- 2026-10-30: built in S17 Lane 2; tests run in the end review.
- 2026-11-01: merged to main in #786 (d8cf79f09).
