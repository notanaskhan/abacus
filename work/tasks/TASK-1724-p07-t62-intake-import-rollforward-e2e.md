---
id: TASK-1724
title: P-07-T62 E2E for intake, import and roll-forward
spec: SPEC-332
acceptance_criteria: [AC-23]
risk_zone: green
status: in-review
epic: P-07
plan_key: P-07-T62
branch: s14-p07-t62
created: 2026-10-28
updated: 2026-10-28
---

## Objective
Backlog row P-07-T62: "E2E for intake, import and roll-forward: cli-06-intake.spec.ts, j19 steps 0,
2 and 3, eng-13-roll-forward.spec.ts, bulk import on the fake CCH export." Acceptance: "The specs
pass full stack on staging with INV-1 and INV-5 asserted."

## Plan
- `apps/web/e2e/journeys/cli-06-intake.spec.ts`: CLI-06 i, h (INV-1: a manager clears a hit) and
  g (the committed 212-row CCH export through the file picker; 204 + 8 + 0; "Import 210 records";
  "210 records imported · 2 skipped · 0 new clients").
- `apps/web/e2e/journeys/J19-estate-amended.spec.ts`: j19 0, 2, 3; 1 and 4–8 fixme with owners.
- `apps/web/e2e/journeys/eng-13-roll-forward.spec.ts`: ENG-13 d and e.
- What the walks needed: ENG-13's route (`/engagements/$engagementId/roll-forward`, starts the
  draft; `RollForwardPage`) and the fixture's draft-start handler; CLI-06, ENG-02 and ENG-13 in
  `SCREEN_SCENARIOS`; ENG-02 prospect's three work items; the harness persona Laura Kemp; CLI-06's
  gallery artboard height (its axe spec read every state hidden).
- DEC-813.

## Acceptance
| Check | Test |
|---|---|
| CLI-06 i, h, g walk with axe and INV-1–5 | `cli-06-intake.spec.ts` (fixture project) |
| J19 0, 2, 3 walk with axe and INV-1–5 | `J19-estate-amended.spec.ts` (fixture project) |
| ENG-13 d, e walk with axe and INV-1–5 | `eng-13-roll-forward.spec.ts` (fixture project) |
| The route page starts, resumes and refuses | `ENG-13.test.tsx` (3 new) |
| ENG-02 prospect's work items | `ENG-02.test.tsx` (1 new) |
| CLI-06 a–i axe | `e2e/screens/CLI-06.spec.ts` (9 pass after the artboard fix) |
| Full stack on staging | fixme with the reason (DEC-813): flags off in E0, no staging |

## Progress log
- `2026-10-28` — Built. Fixture project: the three new specs plus gates-access and eng-cli-core,
  15 passed, 5 fixme. CLI-06 screen spec 9/9 and ENG-13 5/5 (chromium, axe). Vitest: ENG-13 17,
  ENG-02 30, fixtures/gallery/routes suites green. The row's "full stack on staging" is not met
  and cannot be here: the four flags are off in E0 and staging does not exist (DEC-813).

## Handoff
- **Current state:** PR open, held for the batch (stacked on P-07-T54, #582).
- **Next:** when the demo firm turns the P-07 flags on and seeds the Thornbury holdout and an
  archived Northwind PY2025, drop the `test.fixme(project !== "fixture")` lines and run
  `make journeys-full`.
