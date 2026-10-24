---
id: TASK-1186
title: "A-02-T03: C9 v1 contract stub (AUD-06 family) - view by layer, leadsheet by area, Open in Excel and issue link as 501 stubs behind ledger.tb_workpaper; docs/contracts/c09-ledger.md"
spec: SPEC-333
acceptance_criteria: [AC-26, AC-27, AC-28, AC-29]
risk_zone: red
status: in-progress
epic: A-02
plan_key: A-02-T03
branch: s8a-tb-of-record
created: 2026-10-25
updated: 2026-10-25
---

## Objective
"Every route answers 501 under its one matrix action, the api-client regenerates, and the typed fixtures foot to 16,812,400.00 and 14,228,500.00." (A-02-T03)

## Plan (red zone)
- **Already live (SPEC-309, SPEC-310, SPEC-311)**: TB list, adopt, view (`?version=&layer=`), candidates, re-version, all-area leadsheets, annotations, sign-offs, and the tie-out checks list, define and edit. They stay live and ungated (DEC-314); their shapes are C9 v1's for those operations.
- **New stubs** in `backend/src/abacus/modules/assurance/tb_contract.py` (models first, then routes), each authorising its one action on the engagement before the flag answers (DEC-261's order), 404 with `ledger.tb_workpaper` off, 501 `not_implemented` on:
  - `GET …/trial-balances/{tb_id}/layers/{layer}?version=` (`trial_balance.read`): the AUD-06 view by layer (groups, lines with BOY, EOY and layer columns, tick and chip facts, citation ids, flags; named totals; per-layer balance; provenance facts; checks summary; `allowed_actions`, `version`);
  - `GET …/trial-balances/{tb_id}/leadsheets/{area}?layer=&version=` (`trial_balance.read`);
  - `GET …/trial-balances/{tb_id}/export.xlsx?layer=` (`trial_balance.export`);
  - `POST …/trial-balances/{tb_id}/checks/{check_id}/issue-link` (`tie_out_check.define`; `Idempotency-Key`; 201).
- Label and layer fields use C2's generated `TrialBalanceLabelStatus` and `TrialBalanceLayerStatus`; every field is classified.
- `make regenerate` (OpenAPI, api-client, route introspection); closed lists: creating routes in `tests/unit/api/test_app_gates.py`.
- **Tests**: `backend/tests/contracts/c09_ledger/test_c09_stub.py` (one action per route, 404/501, classification, Idempotency-Key, human-only define and export); `apps/web/src/fixtures/seed/trial-balance.ts` (Northwind E0 view, typed with the generated client, derived from the seed's TB and the Harborline report) and `apps/web/src/fixtures/contracts/c09-ledger.contract.test.ts` (foots to 16,812,400.00 and 14,228,500.00, balances, validates against OpenAPI).
- **Docs**: `docs/contracts/c09-ledger.md`; register row C9 -> stub.
- **Rollback**: revert; the live SPEC-309 routes are untouched.

## Progress log
