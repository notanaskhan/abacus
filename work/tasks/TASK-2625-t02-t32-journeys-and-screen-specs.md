---
id: TASK-2625
title: T-02-T32 journey E2E (j06 2/4/5/10, j07 8, j08 12/16, j13 7-8) and the six screens at 1400 and 390
spec: SPEC-502
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: green
status: in-review
epic: T-02
plan_key: T-02-T32
branch: s21-t02-t32
worktree: /Users/ayushkbhatia/Accrued/abacus-s21
created: 2026-11-01
updated: 2026-11-01
---

## Objective
"Every named step passes on staging and on the production canary with INV-1 to INV-5 asserted."
(T-02 §2 "Journeys advanced"; F-04-T21 harness.)

## Scope
- `e2e/journeys/J06-individual-1040.spec.ts`: j06 2 (Claire on /questions, POR-05 a → c), j06 4
  (TAX-03 a → b), j06 5 (TAX-03 a draft chip, TAX-02 a banner), j06 10 (TAX-03 d, TAX-02 e).
- `e2e/journeys/J07-trust-1041.spec.ts`: j07 8 (Nora on /k1s, POR-13 a; no Theo, no 1041).
- `e2e/journeys/J08-partnership-1065.spec.ts`: j08 12 (TXP-12 A4), j08 16 (TXP-12 A5 → B, the
  Pell Street member on POR-13 c without Pell Street II, Meera on POR-13 f).
- `e2e/journeys/J13-partner-review.spec.ts`: j13 7-8 (TAX-03 d, TAX-02 e).
- `e2e/screens/t02-screens-widths.spec.ts`: every artboard of the six screens at 1400 and 390,
  axe zero serious or critical, portal frames without the product's name.
- Wiring: the portal entry's fixture `?screen=` serves POR-05 and POR-13 (install-portal.ts); the
  harness gains the two K-1-only personas (Nora Calloway, the Pell Street member).
**Deviation**: the staging and canary runs are `test.fixme` naming their owner until T-02's live
swaps reach staging (the journey-e2e skill's rule); the fixture project walks every named step.

## Progress log
- 2026-11-01: written; runs at the batch's end review.
