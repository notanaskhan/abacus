---
id: TASK-7610
title: I-02-T02 screen contracts SHL-23 and HOME-05
plan_key: I-02-T02
spec: SPEC-654
acceptance_criteria: [AC-1]  # every artboard with its production or fixture status; every outbound target named
risk_zone: green
status: in-review
branch: i02-t02-screen-contracts
worktree: /Users/ayushkbhatia/Accrued/abacus-s40
created: 2026-11-12
updated: 2026-11-12
---

## Objective
`docs/screens/SHL-23.md` and `docs/screens/HOME-05.md`: every artboard (SHL-23 full and panels
1–7, HOME-05 a–f) with persona, clock, snapshot, prod or fixture status and parity; DF-25's choices;
the deviations; copy keys and the outbound link table.

## Plan
- The two contracts (new). Both screens stay `planned` in the manifest until T15 and T17, so the
  parity tables carry no artboard rows yet (the screen-parity test measures built screens only).
- Rollback: revert.

## Progress log
- `2026-11-12` — Both contracts written. Link-contract test at the S40 end pass.
