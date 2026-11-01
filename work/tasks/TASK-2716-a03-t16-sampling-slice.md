---
id: TASK-2716
title: A-03-T16 part two — the sampling slice through the services
spec: SPEC-580  # A-03 §5.4
acceptance_criteria: [AC-1]
risk_zone: green
status: in-progress
epic: A-03
plan_key: A-03-T16
branch: s22-a03-t16b
worktree: /Users/ayushkbhatia/Accrued/abacus-s22
created: 2026-11-01
updated: 2026-11-01
---

## Objective
- **[AC-1]** "make seed-demo loads every A-03 scenario through the APIs with no content constant
  in code, and fixture mode and seed-demo render identical figures for every state in section
  5.4." **Partly met**: Northwind's Participants path and the firm content load; Granite Peak and
  the equivalence test remain.

## Done
- `sampling` slice (`--slice sampling`, brings `people`, `standards`, `acceptance`):
  BH-EBP-210 Table 2 through the standards import (published); BH FS groupings v1 through the
  taxonomy import (published: 13 groupings, 14 FS lines); Dana's census v1 (409) and v2 (412)
  uploads; Marcus's populations and ties (v1 off by $182,300.00; v2 ties twice), the Participants
  set, and draws with seeds 0x3C77D0 and 0x5E2A91 (25 each; v2's 25 the design's, in order).
- `sampling.draw(..., scenario_seed=)` runs inline (the loader has no worker); synthetic firms only.
- `sampling.api` and `assurance.api` export the services and models the loader uses.
- G2 (DEC-1767, Ayush's call): on Sep 15 Ana Cruz and Kira Ross confirm, Margaret names Dana
  Kowalski the SKE designee and concludes independence; Marcus signs L1 on Version 2 and Hannah
  approves it, as AUD-11 a shows. `review.api` exports `sign_target` for the loader.
- `tests/integration/test_scenario_sampling.py`: loads, checks the figures and both sign-offs,
  reloads writing nothing.

## Remaining
1. Granite Peak FY2026: the 128-account TB (allocated to A-02 §5.3's 14 lines), the mapping set
   and its confirm (the same G2 question), FY2025's prior mapping, and the 1,912 disbursements as a
   GL snapshot with the population and the stratified draw (seed 0x7C31B4).
2. Northwind Distributions (64, "10 of 64 · Draft", seed 0x7B13C4): the design gives no method.
3. `make fixtures export` for these and the fixture-vs-seed-demo equivalence test (§5.4 states).

## Progress log
- 2026-11-01: slice built and its integration test run (1 passed); the G2 conflict found by the
  load, not by a guess.
- 2026-11-01: G2 decided (confirm Ana Cruz earlier); the load also needed Kira Ross's
  confirmation and an SKE designee, both added on Sep 15; test passes with L1 and L2.
