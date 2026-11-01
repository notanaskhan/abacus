---
id: TASK-2215
title: T-02-T11 Python scenario tax slice
spec: SPEC-502
acceptance_criteria: [AC-15, AC-16, AC-17]
risk_zone: amber
status: done
epic: T-02
plan_key: T-02-T11
branch: s17-t02-t11
created: 2026-10-30
updated: 2026-11-01
---

## Objective
The Python scenario's tax slice: 224 TY2025 returns on 214 engagements (10 with two returns)
with statuses 2/8/9/17/15/11/7/10 plus 6 Filed and 139 Accepted, 161 extended, offices
98/64/62, assignments, sync states; golden footing tests; `make fixtures` export.

Acceptance (backlog row): "make seed-demo and fixture mode show identical TAX-01 and TAX-02 data
and every footing test passes."

## Plan (amber)
- `brightwater_hale/tax_board.py` (new): `NAMED`, `DUE`, `build_board`, the `tax_board` slice
  (`NEEDS = ("binders",)`).
- `brightwater_hale/binders.py`: the three board offices in the roster's quota.
- `brightwater_hale/loader.py`: `tax.return_board_set` handler and `SLICE_NEEDS`.
- `abacus_tools/synthetic/fixture_export.py`: slice `tax_board`, flag `tax.returns_v1`, reads
  `tax-returns-summary` and `tax-returns` (stacked on T-02-T09 for the routes).
- Tests: `tests/unit/scenarios/test_t02t11_tax_board.py` (footings, named rows, seed parity).
- To do at the end review: run `make fixtures SNAPSHOT=E0` to commit the two new export files
  (the equivalence test needs them).
- Rollback: revert.

## Acceptance
| Check | Test |
|---|---|
| 224 / 214 / 10 doubles / offices | `test_ac15_returns_*` |
| Status and extension footings | `test_ac15_statuses_*` |
| Named rows, levels, sync | `test_ac15_the_named_rows_hold`, `test_ac16_*` |
| Seed parity, slice shape | `test_ac17_*` |

## Progress log
- 2026-10-30: built in S17 Lane 2 on T-02-T09; export files to generate in the end review.
- 2026-11-01: merged to main in #787 (07c1cdc17).
