---
id: TASK-8753
title: "T-06-T31: TXP-08 states a-e in fixture mode: partner picker, basis cards and reconciliation tile, Pell Street II off tile, inline section 754 DecisionCard with Send to client and Request more analysis, section 752 shares toggle"
spec: SPEC-702
acceptance_criteria: []
risk_zone: green
status: in-review
branch: s51-t06t31
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-20
updated: 2026-11-20
plan_key: T-06-T31
---

## Objective
Send to client shows the existing waiting-on-client issue, and Request more analysis is shown as fixture-only until T-09.

## Plan (green)
1. Seed `fixtures/seed/tax-depth-basis.ts` (the slice's inside share and outside basis per partner; §752 QNR 10,712,500 and other nonrecourse 335,800 by year-end profit %, equal to each partner's §752 share) with a foot test.
2. Handlers: basis?view&partner and the decision-card writes (501) in `handlers/tax-depth.ts`; TXP-08 scenarios on them with `opens` (b, c partner ids, d ?card=754, e ?view=s752).
3. Screen `screens/TXP-08/` (copy, TXP08, Basis live wrapper): view segmented, partner Picker, tally (4 of 5, inside vs outside, §754), basis cards with Pell Street II's off tile, the inline §754 DecisionCard (Elect recommended, Do not elect; the partners decide, so the firm's control is Send to client…, which shows the existing waiting-on-client issue from TXP-10's queue), Request more analysis… marked fixture-only and absent outside fixture builds (DV-3), §752 shares grid.
4. EntityReturn dispatches review/basis to TXP-08 behind tax.entity_depth (basis joins the built set); gallery registers TXP-08.
5. Tests: TXP08.test.tsx (one per artboard plus the two acceptance rules).
6. Rollback: revert the PR.

## Progress log
- `2026-11-20` — Built, stacked on #2391; TXP-08 7 tests and the basis foot test pass; all TXP, fixtures, domain/tax, gallery and routes suites pass (1056), tsc and eslint clean. Deviations: handoff folder absent (words from T-06 §2/§3; no parity or axe); the off tile shows 885,225 vs 913,820 without the 28,595 figure because TaxDepthPartnerBasisOut carries no difference and the screen may not subtract (ADR-050), so a `difference` field is a contract follow-up; b shows Jonah Feld's 4,676,125 on both sides, not the 4,428,925 + 564,050 − 316,850 build-up, which the contract does not carry; the §752 grid has no totals row for the same reason. Gates and tests run once at the S51 end pass (build first, test last).
