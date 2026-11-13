---
id: TASK-7814
title: "Full-stack journeys: a Sep 24 nightly pass, and EBP-01's plan facts in the seed (F-01-T08)"
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
Make the J03 steps that TASK-7813 gated live on the full stack. Their data exists on the scenario timeline only after E0.

## Delivered
- **Seed:** the `ebp` slice records Northwind's plan facts on Sep 22 at 9:30 AM, as Marcus Delaney, through EBP-01's edit service (`assurance.api.edit_ebp_plan`). The time is inferred. The figures are EBP-01 a's: PY 2025, QACA, recordkeeper ID 58217, 286 and 301 participants, large-plan filer, PN 001.
- **Harness:** `e2e/harness/snapshots.ts` adds `ABACUS_SEED_SNAPSHOT`, the `@sep24` tag and `seededAt(project, snapshot, why)`. A tagged step is `fixme` on a full stack seeded at another snapshot.
- **Nightly (`e2e.yml`):** the E0 run skips `@sep24`. The same database is then loaded on to `2026-09-24T10:20` with `people ebp ebp2 planning sampling`, and `@sep24` runs. The job timeout is now 75 minutes.
- **Live on the Sep 24 pass:** J03 7 (EBP-06) and J03 7b (EBP-01).
- **Still gated, with sharper reasons:**
  - J03 12 (EBP-03): no slice records the `ebp_eligibility` attribute test, with its census and HR imports and the verified entry rule.
  - J04 trace and pbc-ai: no slice seeds a Granite Peak upload screened by the v2 run with a C3 proposal; Hannah Leclerc is not on Granite Peak's team; and AUD-01's row opens AUD-02, not AUD-03.
  - J17 0: TASK-7813's reason stands.

## Progress log
- 2026-11-13: built and run locally as above.
