---
id: TASK-8756
title: "A-08-T37: Parity and accessibility: 29 artboards reported at Tier C with 13 locked, Tier B for T1, T2, T6 and T15-720 frames, Tier D geometry, axe on every scenario, keyboard suites for option tiles, code input, drawers, sheets and grids"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: green
status: in-review
branch: s51-a08t37
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-20
updated: 2026-11-20
plan_key: A-08-T37
---

## Objective
The parity report lists 29 artboards with 13 locked at Tier C and axe reports no serious or critical issue.

## Plan (green)
1. `e2e/screens/gallery-boards.ts` (walkGallery, seriousIn) and `gallery-boards.seed.spec.ts` proving a seeded violation is reported; screen specs AUD-12 (d busy by design), AUD-13, AUD-14, AUD-26 and POR-17 (a, d, e at 1400, a at 390, DV-7 no firm on an expired link), axe in light and forced colors.
2. Gallery: data-artboard wrappers for AUD-12/13/14/26; POR-17 registered on its view read (a open, d expired, e answered).
3. Parity tables in the five contracts: 29 artboards at Tier C, 13 locked per A-08 §5.4, host rows Tier D; AUD-13 and AUD-26 join BUILT_PLANNED.
4. `src/routes/a08-parity-locks.test.ts`: test_ac1 29 rows at C, test_ac2 the 13 locks, test_ac3 host Tier D, plus the G-04-T21 and C-01-T50 locks.
5. Fix the lock wording in the G-04-T21 and C-01-T50 tables: 'locked in …' reads as scheduled to the parser (isLocked), so those rows were not locked; now 'locked; <task>'.
6. Rollback: revert the PR.

## Progress log
- `2026-11-20` — Built, stacked on #2394. Locally (own port): 37 gallery screen tests pass with axe clean in light and forced colors (AUD-12 d is the agent run's skeleton, busy by design); the seeded-violation test fails a nameless button as it should; parity unit tests 80 pass. Found and fixed: the G-04-T21 and C-01-T50 Parity tables said 'locked in <task>', which the report parses as not yet locked. Not done: POR-17 b, c and f are locked but not drawn in the gallery (they need the respondent's typing or Alpine Ridge and Front Range Bank seeds); Tier B/C diffs and Tier D measurement (handoff baselines absent); the keyboard suites for option tiles, code input, drawers, sheets and grids. Gates and tests run once at the S51 end pass (build first, test last).
