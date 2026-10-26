---
id: TASK-1344
title: R-01 Playwright journeys and screen specs (R-01-T21)
spec: SPEC-323
acceptance_criteria: [AC-5, AC-6]
risk_zone: green
status: in-review
epic: R-01
plan_key: R-01-T21
branch: s10c-fe
created: 2026-10-27
updated: 2026-10-27
---

## Objective
J12 steps 4, 5 and 15, J03 4c and 10, the J04-fs-audit PBC slice on POR-04, J15 5 (fixture only),
and the POR-03, POR-04 and POR-14 screen specs at 1400 and 390 with axe and the white-label checks.

## Plan
- `fixtures/install-portal.ts`: each journey persona's documents (Claire POR-03 a, Dana POR-03 i,
  Sam POR-14 a) beside sign-in and home.
- Journeys: J12 (rewrite 4, 5; add 15), J03 (new: 4c, 10), J04 (step 3 on POR-04), J15 (new: 5).
- Screens: `POR-04.spec.ts`, `POR-14.spec.ts` (new); POR-03's twelve states at 1400 and 390.
- DEC-444.

## Progress log
- 2026-10-27: Written; tsc and eslint clean. Not run: Playwright's Chromium does not match
  locally. J04 3 and J15 5 are `fixme` with their reasons (no fixture data may be invented).
