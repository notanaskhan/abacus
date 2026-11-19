---
id: TASK-8701
title: "C-01-T51: Journey E2E j10 0-7, j16 8 and j02 7 on the close screens (fixture project)"
spec: SPEC-655
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
branch: c01-t51-journeys
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-19
updated: 2026-11-19
plan_key: C-01-T51
---

## Objective
The J10 read-only path (j10 0, 1, 3, 3b, 4, 4d, 5, 5b, 6, 7), j16 8 and j02 7 walk the close screens on their live routes with each screen's own fixture scenario; journey.step runs axe and INV-1 to INV-5 after every step.

## Plan (green)
1. Register CLS-01, 02, 03, 04, 05, 06, 09 and 10 in fixtures/screen-scenarios.ts with the ids their routes open (closeId, accountRef, clientId); September for CLS-02 c and CLS-03 f.
2. Register POR-11 a, b, c in the /components gallery (portal artboards; b opens the Sound Electric sheet).
3. J10 spec: a `J10 · C-01 read-only path` block; J16 `j16 8`; J02 `j02 7` (drafting half).
4. Every new test is fixture-only (`test.fixme` elsewhere) until C-01-T44's partials (fake QBO company, statements, runs, planner v1) are seeded; staging and the production canary runs are human.

## Progress log
- `2026-11-19` — Built the scenario registrations, the gallery entry, c01-support.ts and the journey steps. j10 2 stays P-06's fixme. Not run yet (S51 end pass). Staging and canary runs, and the full-stack project, wait on C-01-T44's partials and the batch deploy. Gates and tests run once at the S51 end pass (build first, test last).
