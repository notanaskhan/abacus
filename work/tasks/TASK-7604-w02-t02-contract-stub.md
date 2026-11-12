---
id: TASK-7604
title: W-02-T02 C6 workbench-sessions stub (list, create, rename, delete, context; fixtures)
plan_key: W-02-T02
spec: SPEC-653
acceptance_criteria: [AC-L1, AC-L2, AC-L3, AC-V1, AC-C3, AC-C4, AC-R2, AC-R4]  # shapes and fixtures; behaviour T09, T10, T20
risk_zone: amber
status: in-review
branch: w02-t02-stub
worktree: /Users/ayushkbhatia/Accrued/abacus-s40
created: 2026-11-12
updated: 2026-11-12
---

## Objective
The workbench-sessions family as a contract stub, additive to C6 v2: typed models with
classification tags, routes answering 501 under their matrix action behind `workbench.enabled`,
the regenerated client, E0 fixtures for every artboard that reads the family, the contract doc.

## Plan
- `workbench/sessions_contract.py`: `SessionSummaryOut` gains the WB-01 row fields (optional, so
  TAX-08's list keeps its shape); `SessionListOut` gains `next_cursor`, `total`, `counts`;
  `SessionCreateIn.subject_ref` optional (blank session); the list takes `filter`, `q`, `cursor`.
  Without `subject_ref` both answer `workbench.enabled` 404, then 501. `workbench_gate` helper.
- `workbench/list_contract.py` (new): rename (`If-Match`), delete, context options, attach,
  remove; registered in `workbench/api.py` `ROUTERS`.
- `docs/contracts/workbench-sessions.md` (new); register note on C6 in `docs/contracts/README.md`.
- `make generate` (client types for the family and T03's agents routes).
- Fixtures `apps/web/src/fixtures/seed/workbench.ts`, footed by
  `apps/web/src/fixtures/workbench.foot.test.ts` (counted from `e0.tax-returns.json`).
- Rollback: revert; the flag is off and nothing calls the W-02 paths.

## Deviations (DEC-4604)
- The list and create keep their paths and extend additively instead of new routes: TAX-08's
  `?subject_ref=` list and subject create stay as they are.
- The epic's "fixture-backed stubs": the routes answer 501 (the stub convention); the fixtures
  live in the frontend's fixture mode (W-02-T08 mounts them).
- `ContextItemOut.card_title` carries the stack card's heading so the screen never derives it.

## Progress log
- `2026-11-12` — Stub, contract doc and fixtures built (DEC-4604). Tests run at the S40 end pass.
