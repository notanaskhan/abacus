---
id: TASK-7952
title: "I-02-T21: journeys, parity and accessibility (j13 and j23 step 1, j20 step 8 fixme, today.spec.ts, Tier C report, Tier D)"
plan_key: I-02-T21
spec: SPEC-654  # I-02 §3, §5
acceptance_criteria: [AC-11]  # named scenarios pass on staging with INV-1..INV-5 and axe; parity recorded in both contracts
risk_zone: green
status: in-review
branch: i02-t21-today-journeys
worktree: /Users/ayushkbhatia/Accrued/abacus-s43
created: 2026-11-14
updated: 2026-11-14
---

## Objective
Prove the Today brief end to end. Finishes the S42 Tier D partial for HOME-05 and SHL-23.

## Plan
- Journeys: `e2e/journeys/J13-partner-review.spec.ts` (j13 1 Today), `J23-audit-partner-morning
  .spec.ts` (j23 1 Today), `J20-group-audit.spec.ts` (j20 8 `test.fixme` until A-09). The
  harness's steps assert INV-1 to INV-5 and run axe.
- `e2e/home/today.spec.ts`: HOME-05 a–f and SHL-23 full, 1–7 axe; flag off; collapse; building
  and quiet; the drill-in's reserved item.
- Parity: Tier C entries for HOME-05 a–f, SHL-23 full and frame 1 (report-only, masks recorded);
  `e2e/visual/tier-d-today.spec.ts` (Tier D).

## Partial
- Staging walks (DF-04 on a non-synthetic tenant, Grace, walls, the rebuild limit) and the API
  journey test run with I-02-T22's rollout on staging; parity percentages are recorded in the
  screen contracts when the visual project runs at the end pass.

## Progress log
- 2026-11-14: written, not run (S43 end pass).
