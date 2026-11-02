---
id: TASK-3001
title: N-04-T02 notices v1 contract stubs and screen contracts
spec: SPEC-000  # row
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: N-04
plan_key: N-04-T02
branch: s25-n04-t02 (stacked on s25-n04-t01)
worktree: /Users/ayushkbhatia/Accrued/abacus-s25
created: 2026-11-02
updated: 2026-11-02
---

## Objective
- **[AC-1]** "Stubs merge in the Oct 21 batch and freeze Oct 29, and all three screens build in
  fixture mode against them."

## Plan (amber)
- `notices/contract.py`: every `/v1/notices*` and `/v1/notice-intakes*` route (N-04 §4.3),
  classified models, client 404, flag 404, 501; mounted through `notices/api.py` `ROUTERS`.
- `make generate` (OpenAPI + client); check no existing schema was renamed.
- `docs/contracts/notices.md` + register row; `docs/screens/NOT-01.md`, `NOT-02.md`, `NOT-03.md`.
- Contract requests to providers and the pen test 2 note in the contract doc.
- Rollback: revert; the routes 404 with the flag off.

## Acceptance
| Check | Test |
|---|---|
| Every route: client 404, flag-off 404, 501 behind the flag | `tests/contracts/notices/test_n04t02_stub.py` |
| Every route declares its matrix action | route introspection suite |
| Tri and sealed fields classified | same file |

## Progress log
- 2026-11-02: built; client regenerated (additions only). Tests at the S25 end review.

## Decisions made during this task
DEC-2051.
