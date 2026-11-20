---
id: TASK-8751
title: "T-06-T29: TXP-03 states a, a2, b, c, d and e in fixture mode on T6: Register, By property and Dispositions segments, tally strip, DataTable statement with property group rows, Flag and Check chips, Asset detail O2 drawer with class and bonus pickers producing a ghost value, section sign-off with note"
spec: SPEC-702
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: green
status: in-review
branch: s51-t06t29
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-20
updated: 2026-11-20
plan_key: T-06-T29
---

## Objective
Each artboard renders from its scenario, and the sign-off dialog requires a note while the roof flag is open.

## Plan (green)
1. Seed `fixtures/seed/tax-depth-assets.ts` (the T-06-T22 Ridgeline slice's register, land and Form 8825 by property, typed as TaxDepthFixedAssetsOut; variants e0, bonusResolved, signedOff) with a foot test.
2. Handlers `fixtures/handlers/tax-depth.ts` (fixed-assets reads, sections with fixed-assets, writes 501) over the T-05 workbook handlers; TXP-03 scenarios on it, with `opens` (a2 ?asset, b ?view=by_property, d ?view=dispositions).
3. Screen `screens/TXP-03/` (copy, TXP03 pure component, FixedAssets live wrapper): control bar, tally strip, statement register with property group rows, Flag and Check chips, O2 Asset detail drawer with class and bonus Pickers producing a ghost proposal (fixedAssetChange C3), sign-off with a required note while a flag is open.
4. EntityReturn dispatches review/fixed-assets to TXP-03 behind tax.entity_depth; EntityReturnLayout takes a `built` set so landed P1 sections render and join the 7-option track (DEC-5741); gallery registers TXP-03 and passes each state's opens.
5. Tests: TXP03.test.tsx (one per artboard, scenario server state, the note rule).
6. Rollback: revert the PR; flag tax.entity_depth stays off in production.

## Progress log
- `2026-11-20` — Built, stacked on #2389; TXP-03 9 tests, seed foot 3, TXP-00/domain/scenario suites pass, tsc and eslint clean. Deviations: handoff folder absent, so words follow T-06 §2/§3 and the TXP-07 grammar (column headers, EmptyState body, drawer lines) and parity and axe are not run; placed-in-service shows month and year (the contract carries a date, the handoff mixes 'Apr 2018' and 'Mar 10, 2025'); the drawer's evidence button opens SHL-08 by asset id because the contract row names no document. Gates and tests run once at the S51 end pass (build first, test last).
