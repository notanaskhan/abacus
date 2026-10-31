---
id: TASK-2220
title: T-02-T12 TAX-01 practice board a–g
spec: SPEC-502
acceptance_criteria: [AC-7]
risk_zone: green
status: done
epic: T-02
plan_key: T-02-T12
branch: s17-t02-t12
created: 2026-10-30
updated: 2026-11-01
---

## Objective
TAX-01 states a–g on TPL-01's T1 IndexList: tiles as filters, office grouping bands, bulk
selection bar with Assign preparer live (planned items fixture-only), filtered and season empty
states, skeletons, due popover, Draft K-1 popover naming TXP-12, sync chip naming TAX-09, signer
chips naming SIG-01; the fixture handler answers as the live routes do (T-02-T09).

Acceptance (backlog row): "Seven scenarios pass their tests and axe and production builds show no
Board toggle, Extend or Run firm standards item."

## Plan
- Contract (additive): `TaxReturnRowOut.issues`, `TaxReturnRowOut.signers`
  (`TaxReturnSignerOut`); `make generate`.
- `fixtures/handlers/tax-returns.ts`: rows from the TY2025 seed with the server's filters, sort
  allowlist and office grouping; summary per tax year; bulk-assign.
- `screens/TAX-01/{index.tsx, copy.ts, scenarios.ts}`, `fixtures/scenarios/TAX-01.ts`.
- Route `/tax-returns` behind `tax.returns_v1` (`routes/firm/tax-returns.tsx`); nav area routed;
  manifest `fixture`; gallery entry.
- Tests: `TAX-01.test.tsx` (a–g, tiles, assign, error), `TAX-01.production.test.tsx`.
- Rollback: revert; the route falls back to the area's flag-off landing.

## Acceptance
| Check | Test |
|---|---|
| a–g render their data condition | `TAX-01 artboards` |
| Assign preparer posts `:bulk-assign` with an Idempotency-Key | `d: three returns selected…` |
| Production: no Board toggle, Extend or Run firm standards | `TAX-01.production.test.tsx` |
| Axe | end review (gallery axe sweep) |

## Progress log
- 2026-10-30: built in S17 Lane 2 on T-02-T11; tests run in the end review.
- 2026-11-01: merged to main in #792 (f2d0625e8).
