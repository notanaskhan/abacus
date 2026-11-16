---
id: TASK-8328
title: "T-07-T30: Journey E2E j07 steps on the fixture project"
spec: docs/plan/epics/T-07.md §2
acceptance_criteria: [T-07-T30]
risk_zone: green
status: in-review
branch: t07-t30-j07-journey
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-16
updated: 2026-11-16
plan_key: T-07-T30
---

## Objective
Journey E2E j07 steps on the fixture project.

## Plan (green)
1. `apps/web/e2e/journeys/J07-trust-1041.spec.ts`: steps 1 and 3 (TXT-01, TXT-02 artboards), 5 and 7 (TXT-03: the allocation foots, Release disabled at the [H] gate, then released), with T-02-T32's step 8 (Nora sees only her K-1); staging stays `test.fixme` naming its owner.

## Progress log
- `2026-11-16` — Built in the S47 sequential stack. eslint clean; the Playwright run is the end pass's. Partial: the full-stack and staging projects, the agents-off variant and j19 steps 4 and 5 are not added (they wait on T-07's live swaps). Gates and
  tests run once at the S47 end pass (build first, test last).
