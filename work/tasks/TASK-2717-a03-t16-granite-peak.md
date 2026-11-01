---
id: TASK-2717
title: A-03-T16 part three — Granite Peak FY2026 through the services
spec: SPEC-580  # A-03 §5.4
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: A-03
plan_key: A-03-T16
branch: s22-a03-t16c
worktree: /Users/ayushkbhatia/Accrued/abacus-s22
created: 2026-11-01
updated: 2026-11-01
---

## Objective
Granite Peak Outdoor Supply FY2026 in the `sampling` slice, through the services as the people the
design names: the 128-account trial balance, its mapping and Caleb Dunn's confirm (AUD-31 f), and
the 1,912 disbursements as a GL snapshot with the population and the stratified draw (AUD-11 f).

## Acceptance criteria
- **[AC-1]** "make seed-demo loads every A-03 scenario through the APIs with no content constant
  in code, and fixture mode and seed-demo render identical figures for every state in section
  5.4." **Partly met**: Northwind's Participants path (TASK-2716) and Granite Peak load; the
  Distributions set and the equivalence test remain.

## Done (DEC-1768)
- Sep 10: Caleb Dunn added to A2's team, MO, OH, SB, CH and CD confirm, Luis Ferrante created as a
  contact and named SKE designee, Margaret concludes (G2).
- Sep 11: Simone records the NetSuite TB (128 accounts, 71,910,000 each side) and adopts it; the
  rules run on BH FS groupings v1; Caleb confirms (L1, 128 of 128 by number range).
- Sep 24, 10:18 AM: Simone records the subsequent-period GL (3,824 lines), builds the population
  (1,912 / $38,640,200.00, both code ties `tie`), creates "Disbursements" and draws Version 1
  with seed 0x7C31B4: 40 items, the SURL payments in draw order (draft).
- Snapshot `2026-09-24T10:20` (AUD-11 f's clock).
- `assurance.api` exports `adopt_trial_balance`, `MappingRunIn`, `MappingConfirmIn`;
  `sampling.api` exports `GeneralLedgerSourceIn`, `StratumIn`.
- `tests/integration/test_scenario_sampling.py` runs at the new snapshot and checks Granite: 1 passed.

## Remaining
1. FY2025's prior mapping: built in TASK-2718 (DEC-1769) as the predecessor's file.
2. Northwind Distributions (64, "10 of 64 · Draft", seed 0x7B13C4): the design gives no method.
3. `make fixtures export` and the fixture-vs-seed-demo equivalence test (tie labels and
   `account_codes` differ from the C9 fixture today).

## Progress log
- 2026-11-01: built; R-SO-5 refused Caleb's confirm until Granite's G2 was met — the same
  conflict as Northwind's (DEC-1767), found by the load and settled the same way.
  `tests/unit/scenarios/test_scenario_documents.py` fails 4 on main too (not this change).
