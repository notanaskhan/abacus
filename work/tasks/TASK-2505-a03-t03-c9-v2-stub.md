---
id: TASK-2505
title: A-03-T03 C9 v2 contract stub (taxonomy and mapping)
spec: SPEC-580
acceptance_criteria: [AC-16]
risk_zone: red
status: done
epic: A-03
plan_key: A-03-T03
branch: s20-a03-t03
created: 2026-10-30
updated: 2026-10-30
---

## Objective
C9 v2 as a contract stub on the paths AUD-31 will use, beside the live SPEC-316 v0 slice, behind
`ledger.tb_mapping`, with the contract doc `docs/contracts/ledger-mapping.md`.

## Verify first (status: partial)
TASK-5011 documented the live v0 (`c09-ledger.md`, "Taxonomy half, live v0"); TASK-345/5009 built
grouping sets, rule mapping on read, edits, sign-offs and the staleness event. Kept as is.

## Plan (red)
- `assurance/tb_mapping_contract.py`: models (catalogue, picker by class with Recently used,
  mapping-set summary with computed status and tallies, rows, subtotals, run, mapped TB,
  `TbFsLineGroupOut`; inputs run, edit, confirm); routes `GET /v1/grouping-sets/catalogue`,
  `GET /v1/grouping-sets/{set}/versions/{n}/lines`, `GET|POST /v1/engagements/{eid}/mapping-sets`,
  `GET /v1/mapping-sets/{msid}`, `…/run`, `PUT …/accounts/{account_code}`, `POST …/confirm`,
  `GET …/trial-balance`; gates as DEC-1553; mounted in `assurance.api.ROUTERS`.
- `assurance/tb_mapping_fixtures.py`: Granite Peak FY2026 summary and run (128/128, 1 of 1,
  Prepared · CD) only.
- Status vocabulary: `mapping_set` (computed), `account_mapping_state` (with A-09's reserved
  `suggested`, `adopted`); `make regenerate`.
- Docs: `docs/contracts/ledger-mapping.md`; `c09-ledger.md` pointer; register row.
- DEC-1555: paths that collide with v0 (`GET /v1/grouping-sets`, `POST …/imports`) keep v0; the
  catalogue is `/catalogue`; an account mapping is `(mapping_set_id, account_code)`; the adopt
  route is declared, not mounted; `group_by=fs_line` is a model here and wired by T08.
- Rollback: revert; flag-gated, writes nothing.

## Acceptance
| Check | Test |
|---|---|
| Routes, actions, 404/501; v0 unchanged; adopt not mounted | `tests/contracts/c09_ledger/test_c09_v2_stub.py` |
| Fields classified; status words | same |
| Gate order; non-person refused; fixture or 501 | same |

## Progress log
- 2026-10-30: built (tests first, run at the end review). DEC-1555.
