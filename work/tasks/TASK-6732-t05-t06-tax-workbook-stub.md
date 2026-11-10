---
id: TASK-6732
title: "T-05-T06: tax workbook v1 contract stub (32 routes, classified models, contract doc)"
spec: SPEC-651
acceptance_criteria: [AC-0]
risk_zone: amber
status: in-review
branch: s35-t05-t06
worktree: /Users/ayushkbhatia/Accrued/abacus-s35
created: 2026-11-10
updated: 2026-11-10
plan_key: T-05-T06
---

## Objective
The stub merges dark behind tax.entity_workspace with generated client types, and the contract doc lists every human-only action.

## Plan (amber: written before the build)
- **`backend/src/abacus/modules/tax/workbook_contract.py`** (new): the models of T-05 §4.3, every field classified (TRI on values, formulas, memo bodies and partner payloads; no full TIN anywhere), plus 32 route stubs.
  - Order of answers: a client principal 404, the flag off 404, the one matrix action (T-05-T04), then 501.
  - `errors` declare 409 where §4.3 names a conflict.
  - Mounted from `tax/api.py` `ROUTERS`. No operation-id or path clashes (function names prefixed `entity_`).
- **`docs/contracts/tax-workbook.md`** (new): callers and actions, models and classification, status words, every human-only action, errors, audit events, and the three red-service signatures N provides. Plus a row in `docs/contracts/README.md`.
- **Test:** `backend/tests/contracts/tax_workbook/test_tax_workbook_stub.py`. It holds four things:
  - the screens' fields exist on their models;
  - every route is published with its 501;
  - the human verbs deny the agent, and the doc names each;
  - values are tax return information.
- P-10's run API, P-04's sign-off, proposal and issue routes, and A-06's entry routes are reused, not stubbed again.

## Partials (flagged)
- **Generated client types:** `make generate` runs at the S35 end pass (the generated client cannot be hand-edited).
- **"Seed-derived fixtures for all 57 artboards":** the fixture-mode handlers and seed come with each TXP screen's FE row (T-05-T08 onward). The stub publishes the shapes.
- **`account_mapping.propose`:** not in A-03's matrix file yet. The mapping route declares `account_mapping.edit` until then.

## Progress log
- 2026-11-10: built; the app mounts the 32 routes with no clash; tests at the end pass.
