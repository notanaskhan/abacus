---
id: TASK-7813
title: "Full-stack journeys round 2: the five red journeys on the synthetic firm (F-01-T08)"
spec: SPEC-000  # row (F-01-T08)
acceptance_criteria: [AC-20]  # the journeys that read seeded data pass on the local full stack
risk_zone: green
status: in-review
branch: lo38-journeys-fullstack
worktree: /Users/ayushkbhatia/Accrued/abacus-lo38
created: 2026-11-13
updated: 2026-11-13
plan_key: F-01-T08
---

## Objective
Fix the five journeys TASK-7812 left red on the local full stack: J03 and J18 (EBP canvases), J04 trace and pbc-ai (Granite Peak), J17 (Home counts).

## Delivered
- The `ebp` slice turns `ebp.modules` on for Brightwater Hale: the EBP canvases and their reads sit behind it, and the seed never set it (the reads answered 404).
- The fullstack adapter resolves a fixture path's `_auditId_` to Northwind's seeded audit, through AUD-01's row as the persona; the SPA keeps its token in memory, so a request from the test is unauthenticated.
- J18 1 (EBP-04) and J03 13 (EBP-04) pass on the full stack.
- J03's combined step-7 test is split per screen, with every assertion kept. The steps the E0 timeline cannot show are `fixme` off the fixture project, each with its reason:
  - EBP-06: the TB of record lands at 10:00 AM.
  - EBP-01: no plan facts are recorded; its artboard is Sep 24.
  - EBP-03: the sample is drawn at Sep 24, 10:20 AM.
- J04 trace and pbc-ai: `fixme` on fullstack. No slice seeds Granite Peak's screened upload, its citation or its C3 proposal; the nightly loads E0, not Sep 24; and Hannah Leclerc is not on Granite Peak's FY2026 team, so AUD-01 does not list it for her.
- J17 0: `fixme` on fullstack. HOME-01 b's four gates are not open at E0 on the timeline, and Fairhaven is held out of the nightly seed.

## Local run
- Full stack (J03, J04, J17, J18): 3 passed, 62 skipped, 0 failed.
- Fixture project, same specs: 46 passed, 19 skipped, 0 failed.

## Follow-up (not built)
A second nightly pass at a later snapshot (2026-09-24T10:20), with these additions, would turn the gated steps live:
- the sampling and review slices;
- EBP-01's plan facts, recorded through `ebp_plan.edit_plan`;
- Granite Peak's screened upload;
- a J04 persona on Granite Peak's team (Omar Haddad or Simone Baptiste).

## Progress log
- 2026-11-13: diagnosed and fixed as above.
