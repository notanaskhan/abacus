---
id: TASK-7812
title: "Full-stack journeys on the synthetic firm: sign-in race, portal entry, nightly slices, FirmMark a11y (F-01-T08)"
spec: SPEC-000  # row (F-01-T08)
acceptance_criteria: [AC-20]  # the journeys that read seeded data pass on the local full stack
risk_zone: green
status: in-review
branch: lo38-journeys-fullstack
worktree: /Users/ayushkbhatia/Accrued/abacus-lo38
created: 2026-11-12
updated: 2026-11-12
plan_key: F-01-T08
---

## Objective
Make the nightly full-stack journeys run on the synthetic firm (PF-X1): find why they're red, and fix what's real.

## Delivered
- The adapter waits for the sign-in callback; portal personas open the portal entry.
- `e2e.yml` seeds the journeys' slices.
- FirmMark is decorative without a name.
- J09 steps 3 to 6 are `fixme` off fixtures (N-04-T26).
- Needs #1839 (DEC-4809, the notices work classes): without it, the seed's notices slice times out.

## Local run (make dev, make seed-demo with the slices, make journeys-full)
- Before: 14 failed, 14 passed.
- After the fixes: J02, J12, J13, J16, POR-06, J04 pbc 1 and J09 1b pass.
- Still red: J03 and J18 (EBP screens), J04 trace and pbc-ai (Granite Peak's row action), J17 (Home count).

## Progress log
- 2026-11-12: run and fixed as above.
