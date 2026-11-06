---
id: TASK-3318
title: A-07-T11 fixtures and scenarios for AUD-18 to AUD-25
spec: SPEC-000  # row (A-07-T11)
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: A-07
plan_key: A-07-T11
branch: s28-a07-t11
worktree: /Users/ayushkbhatia/Accrued/abacus-s28
created: 2026-11-05
updated: 2026-11-05
---

## Objective
"/components/screens/AUD-25?st=c&frame=1&static=1 reproduces the Thu Dec 3, 2026 4:18 PM CST locked state with seal 7c41…a9e2 from typed data."

## Plan
- `fixtures/seed/audit-completion.ts`, `fixtures/handlers/audit-completion.ts`.
- `fixtures/scenarios/AUD-{18,19,21,22,23,24,25}.ts` + `screens/*/scenarios.ts`: 49 states.
- The gallery route joins with each screen's row (S29 to S34).

## Progress log
- 2026-11-05: built. Tests at the S28 end review.

## Decisions made during this task
None.
