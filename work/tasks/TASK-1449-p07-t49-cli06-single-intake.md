---
id: TASK-1449
title: CLI-06 single intake on O6 over CLI-01 (P-07-T49)
spec: SPEC-332
acceptance_criteria: [AC-23, AC-26]
risk_zone: green
status: in-review
epic: P-07
plan_key: P-07-T49
branch: s11-engagements
created: 2026-10-27
updated: 2026-10-27
---

## Objective
"Scenarios a to f, h and i pass with axe and Create and start acceptance lands on CLI-07."

## Plan
- `screens/CLI-06/{index.tsx,copy.ts,scenarios.ts,CLI-06.test.tsx}`; `domain/clients/intake.ts`
  (generated client); `fixtures/handlers/intake.ts`, `fixtures/scenarios/CLI-06.ts`; route
  `/clients/new` behind `clients.v2` (CLI-07 / CLI-02 / CLI-01 wired in routes/firm); manifest
  live; gallery artboards; axe in `e2e/screens/CLI-06.spec.ts`. DEC-543.

## Progress log
- 2026-10-27: built. Playwright (axe) not run here (chromium mismatch).
