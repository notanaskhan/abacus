---
id: TASK-8057
title: "A-09-T07: fixture scenarios per artboard (AUD-32 to AUD-35, POR-23) with footing tests"
spec: SPEC-658
acceptance_criteria: [AC-0.6]
risk_zone: green
status: in-review
branch: a09-t07-fixture-scenarios
worktree: /Users/ayushkbhatia/Accrued/abacus-s45
created: 2026-11-15
updated: 2026-11-15
plan_key: A-09-T07
---

## Objective
A typed scenario for every lettered artboard, with persona and clock, and footing tests.

## Plan
1. `fixtures/scenarios/group-audit.ts` over `seed/group-audit.ts`.
2. `fixtures/contracts/group-audit-scenarios.test.ts`.

## Progress log
- `2026-11-15` — Planned at the S45 kickoff (TASK-8029).
- `2026-11-15` — Built (DEC-5042). tsc and eslint clean. Tests run at the end pass.
- **Partial:** AUD-31 group renditions and the host states wait for their screens.
