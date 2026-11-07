---
id: TASK-5127
title: A-07-T17 AUD-18 EQR workspace in fixture mode, a to e
spec: SPEC-000  # row (A-07-T17)
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: A-07
plan_key: A-07-T17
branch: s29-a07-t17
worktree: /Users/ayushkbhatia/Accrued/abacus-s29
created: 2026-11-06
updated: 2026-11-06
---

## Objective
AUD-18 on T2: rail checklist, digest cards with Mark reviewed, dock Notes and Agent, Concur sheet with the attestation, Concurred card, the Not the EQR state.

## Plan
screens/AUD-18/Workspace.tsx, copy, test; route /audits/$auditId/eqr; manifest fixture; screen-scenarios. Aligns the A-07-T11 seed's letters with the screen contract.

## Progress log
- 2026-11-06: built. `apps/web/src/screens/AUD-18/AUD-18.test.tsx` written, not run (end pass). tsc and eslint clean.

## Decisions made during this task
DEC-2423
