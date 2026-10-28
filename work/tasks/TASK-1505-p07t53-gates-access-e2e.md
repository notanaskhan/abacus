---
id: TASK-1505
title: P-07-T53 E2E for gates and access (CLI-04, CLI-07, CLI-08, ENG-05, J03 1-2)
spec: SPEC-332
acceptance_criteria: [AC-24]
risk_zone: green
status: in-review
epic: P-07
branch: s12b-p07t53
created: 2026-10-27
updated: 2026-10-27
---

## Objective
Journey specs for P-07's gates and access with INV-1 and INV-4 asserted, fixture-first (DEC-645).

## Done here
- `apps/web/e2e/journeys/gates-access.spec.ts`: CLI-04 a/c, CLI-07 b/a/d, CLI-08 e/f, J03 1 and 2 in the fixture project; fullstack and staging fixme until P-07-T62; the portal invite step and ENG-05's refusal fixme with owners.
- CLI-04, CLI-07, CLI-08 registered in `screen-scenarios.ts` with the ids their routes need.

## Progress log
- 2026-10-27: written; eslint, prettier and tsc clean. Run in the S12 batch test pass (`make journeys`).
