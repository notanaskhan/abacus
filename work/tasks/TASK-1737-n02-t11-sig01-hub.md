---
id: TASK-1737
title: N-02-T11 SIG-01 Signatures hub (fixture mode)
spec: SPEC-381
acceptance_criteria: [AC-4]
risk_zone: green
status: in-review
epic: N-02
plan_key: N-02-T11
branch: s14-n02-t11
created: 2026-10-28
updated: 2026-10-28
---

## Objective
SIG-01 on T1 with the O2 drawer in fixture mode. Acceptance (backlog row): "Scenario tests for a,
b, c, d, e and g pass at 1400 with the DF-11 copy in the E2 drawer and no Send new link at
unlock."

## Plan
- `screens/SIG-01/{index.tsx,copy.ts,scenarios.ts,SIG-01.test.tsx}`; gallery registration;
  `fixtures/scenarios/SIG-01.ts`. DEC-827 (drawer evidence and trail with T13; r with T15).

## Progress log
- `2026-10-28` — Built on N-02-T10. tsc, eslint, prettier clean. Tests written, not run.

## Handoff
- **Current state:** PR open, held for the batch, stacked on #611.
- **Next:** N-01-T10.
