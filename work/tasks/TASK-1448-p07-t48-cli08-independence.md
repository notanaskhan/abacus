---
id: TASK-1448
title: CLI-08 Independence and conflicts (P-07-T48)
spec: SPEC-332
acceptance_criteria: [AC-13, AC-28]
risk_zone: green
status: in-review
epic: P-07
plan_key: P-07-T48
branch: s11-engagements
created: 2026-10-27
updated: 2026-10-27
---

## Objective
"Scenarios a to g and the declined-note state pass with axe and Conclude is disabled for everyone
but the engagement partner."

## Plan
- `screens/CLI-08/{index.tsx,copy.ts,scenarios.ts,CLI-08.test.tsx}`; `domain/engagements/
  independence.ts` (generated client); `fixtures/handlers/independence.ts`,
  `fixtures/scenarios/CLI-08.ts`; route `/clients/$clientId/independence/$engagementId` behind
  `engagements.acceptance_v2`; manifest live; gallery artboards; axe in
  `e2e/screens/CLI-08.spec.ts`. Deviations in docs/screens/CLI-08.md; DEC-542.

## Progress log
- 2026-10-27: built. Playwright (axe) not run here (chromium mismatch).
- 2026-10-27: targeted test pass green (see the S11 lane 4 report); gates run once (ruff, pyright, lint-imports, quality modules, check-generated, tsc, eslint, prettier). Playwright skipped (chromium mismatch).
