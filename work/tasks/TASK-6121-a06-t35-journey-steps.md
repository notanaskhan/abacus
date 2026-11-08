---
id: TASK-6121
title: "A-06-T35 journey steps j03 13, 14, 16, j04 13, j05 4, j22 8 on the completion screens"
spec: SPEC-000  # row (A-06-T35)
acceptance_criteria: [AC-1]
risk_zone: green
status: done
epic: A-06
plan_key: A-06-T35
branch: s30-a06-t35
worktree: /Users/ayushkbhatia/Accrued/abacus-s30
created: 2026-11-08
updated: 2026-11-08
---

## Objective
Journey E2E steps with assertInvariants and axeStep (the harness) for A-06's screens; fixme until A-08's AUD-26 for the full-stack run.

## Plan
- `apps/web/e2e/journeys/J03-ebp-audit.spec.ts`: j03 13 (AUD-16 a), j03 14 (AUD-17 a), j03 16 (AUD-20 a: 63 of 63 tie, 142 checklist items), fixture project live, full stack fixme.
- `J04-fs-audit.spec.ts`: j04 13 (AUD-20 d, client preview without the checklist).
- `J05-ssars.spec.ts`, `J22-unrecorded-liabilities.spec.ts`: j05 4 and j22 8 fixme until AUD-26 and their scenarios.

## Progress log
- 2026-11-08: built. Written, not run (tests at the end review). eslint and prettier clean.

## Decisions made during this task
None.
