---
id: TASK-6221
title: A-05-T61 journey steps j03 12a, 12b and j04 11; parity Tier C rows; axe
spec: SPEC-640
acceptance_criteria: [AC-1]  # j03 12a, 12b and j04 11 pass on staging with INV-1 to INV-5; parity covers the 51 artboards
risk_zone: green
status: in-review
epic: A-05
plan_key: A-05-T61
branch: s31-a05-t61
worktree: /Users/ayushkbhatia/Accrued/abacus-s31
created: 2026-11-08
updated: 2026-11-08
---

## Plan
- Journey steps (axeStep and INV-1 to INV-5 through the harness), on fixtures:
  - J03 12a (EBP-08) and 12b (EBP-07 a and d) in `e2e/journeys/J03-ebp-audit.spec.ts`;
  - J04 11 (AUD-27) in `e2e/journeys/J04-fs-audit.spec.ts`.
- `fixtures/screen-scenarios.ts` registers EBP-07, EBP-08 and AUD-27 for `?screen=` (Northwind's audit), and its test lists them.
- Parity: the screen contracts carry Tier C for EBP-05, 07, 08, 09 and AUD-27, and the Tier C lock on EBP-07a.

## Partial
- Staging: the steps are fixme off the fixture project until the S31 batch is on staging (and the
  DEC-1389 gates hold for live firms).
- Parity measurement: the five screens have no `/components/screens/<ID>` gallery artboards and no
  parity-manifest baselines yet. Until both exist, the parity report can't measure them and
  parity.json doesn't cover the 51 artboards.

## Progress log
- 2026-11-08: built; runs at the S31 end pass.
