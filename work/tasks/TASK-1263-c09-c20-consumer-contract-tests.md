---
id: TASK-1263
title: Consumer contract tests for C9 v1 and C20 v1 - pytest in c09_ledger and c20_integrations, TypeScript fixture assertions (A-02-T08)
spec: SPEC-333
acceptance_criteria: [AC-5, AC-17, AC-29, AC-30, AC-35, AC-38]
risk_zone: amber
status: in-review
epic: A-02
plan_key: A-02-T08
branch: s9a-contract-stubs
created: 2026-10-26
updated: 2026-10-26
---

## Objective
"Both suites run in N's CI against the stubs and assert shapes, refusal codes, registry status
words, agent refusal and the seed figures" (A-02-T08).

## Plan (amber: tests only)
- `backend/tests/contracts/c09_ledger/test_c09_consumers.py`: AUD-06's view of C9 v1 - the
  Northwind seed figures fit `TbLayerViewOut` and foot; labels and layers are the registry's;
  the documented refusal codes are declared (409 on the layer view, 501 until built); every
  C9 action denies the agent.
- `backend/tests/contracts/c20_integrations/test_c20_consumers.py`: POR-16's view of C20 v1 -
  the Copperleaf cards (a, d, g) fit the models with registry status words; refusals
  (`authorization_required`, `consent_version_stale`, `ledger_already_connected`,
  `connector_not_available`) are the contract's; every action denies the agent; no write scope.
- `apps/web/src/fixtures/contracts/c20-integrations.contract.test.ts`: the POR-16 fixtures match
  the OpenAPI document, carry registry words and no posting copy (DF-19); handlers refuse a start
  without the authorization.
- No production code. Rollback: revert.

## Progress log
- 2026-10-26: built. `tests/contracts/c09_ledger` 82 passed (consumers 29 new: Northwind E0
  figures against the golden, decimal strings, the Investments leadsheet 18.4 %, registry enums,
  the eight live refusals in the catalogue, agent refusal, no hidden counts);
  `tests/contracts/c20_integrations` 43 passed (consumers 12); vitest
  `c20-integrations.contract.test.ts` 7 passed. `layer_unbalanced` is documented but registers
  with A-02-T07, so the consumer suite checks only the live refusals.
