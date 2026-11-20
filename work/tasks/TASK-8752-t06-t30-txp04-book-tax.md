---
id: TASK-8752
title: "T-06-T30: TXP-04 states a, a-prime, b, c and d in fixture mode: M-1/M-3 and Schedule M-2 tab frames, M-3 row selection and no-difference collapse, M-1 reference banner, As drafted and With proposed fix toggle, ghost chip with Accept to SHL-10 and Reject with reason, accepted state with checkpoint link"
spec: SPEC-702
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: green
status: in-review
branch: s51-t06t30
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-20
updated: 2026-11-20
plan_key: T-06-T30
---

## Objective
M-1 never renders as filed, and Accept opens SHL-10 rather than applying the value inline.

## Plan (green)
1. Seed `fixtures/seed/tax-depth-booktax.ts` (M-3 with one permanent 6,200 row and a collapsed no-difference row, the M-1 reference not filed, T-05's M-2 as drafted and with the fix; accepted variant) with a foot test.
2. Handlers: m3, m1 and m2?variant in `handlers/tax-depth.ts`; TXP-04 scenarios on them (d: accepted, issues d), with `opens` (a′ ?m1=1, c ?variant=with_fix) and a per-state Group B frame.
3. Screen `screens/TXP-04/` (copy, TXP04 with the M-1/M-3 and Schedule M-2 frames, BookTax live wrapper): Part I key-values, Parts II–III statement grid, M-1 toggle with banner and Not filed pill, As drafted · With proposed fix, tally against Schedule L, ghost on line 4 with Accept… (opens SHL-10's ApproveSheet on the M-2 issue's fix proposal) and Reject… with a required reason, the accepted state with Open checkpoint (Activity).
4. EntityReturn dispatches m1-m3 and schedule-m2 to TXP-04 behind tax.entity_depth (m1-m3 joins the built set); gallery registers TXP-04 with each state's frame.
5. Tests: TXP04.test.tsx, one per artboard plus the two acceptance rules.
6. Rollback: revert the PR.

## Progress log
- `2026-11-20` — Built, stacked on #2390; TXP-04 7 tests and the book-tax foot test pass, scenario and TXP-00/03 suites pass, tsc and eslint clean. Deviations: handoff folder absent (words from T-06 §2/§3 and the form's line captions; no parity or axe); M-3 Parts II–III carry only the tax-exempt row and one 'Other items with no differences' row (1,256,200 − 6,200), because the slice names no other line, and no figure was invented; d reads 'Fix approved · checkpoint saved' instead of 'Approved by Samuel Ito · 9:51 AM' because no route returns the proposal's decider and time yet; the checkpoint link opens the return's Activity (TAX-07) since SHL-16 has no typed route here. Gates and tests run once at the S51 end pass (build first, test last).
