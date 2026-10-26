---
id: TASK-1342
title: CLI-07 Acceptance and continuance, verified against the row (P-07-T46)
spec: SPEC-332
acceptance_criteria: [AC-2, AC-6, AC-7, AC-11]
risk_zone: green
status: in-review
epic: P-07
plan_key: P-07-T46
branch: s10c-fe
created: 2026-10-27
updated: 2026-10-27
---

## Objective
"Scenarios a to g pass with axe and only the engagement partner sees an enabled Decide control."
The screen itself landed in #437 (TASK-1328: fixtures, DecisionDock, route, manifest live,
gallery, `e2e/screens/CLI-07.spec.ts`), over the acceptance routes of #437/#438.

## Plan
- Check the built screen against the row: generated client only (`domain/engagements/acceptance.ts`
  over `@abacus/api-client/query`), a–g scenarios with tests, the partner-only Decide test, the
  step-up, the locked view, the axe spec for a–g.
- Run its vitest file in the final pass. No code change unless a gap shows.

## Progress log
- 2026-10-27: Nothing missing against the row: a, b, d, e, f live; c and g fixture-only; the
  partner-only Decide, rationale rule, MFA step-up and locked view are tested in
  `screens/CLI-07/CLI-07.test.tsx`; the axe spec exists but was not run (Playwright's Chromium does
  not match locally). The contract's open gap (flag source names, SHL-08 planned) is unchanged.
