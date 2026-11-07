---
id: TASK-5124
title: A-05-T44 EBP-05 Distributions and Loans canvas, a to e
spec: SPEC-000  # row (A-05-T44)
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: A-05
plan_key: A-05-T44
branch: s29-a05-t44
worktree: /Users/ayushkbhatia/Accrued/abacus-s29
created: 2026-11-06
updated: 2026-11-06
---

## Objective
EBP-05 on T6 in the AUD-02 cockpit: segmented control, tally strip, loan and offset cards, new-loan limits, sampled distributions; agent ticks outlined until adopted.

## Plan
screens/EBP-05 (Loans.tsx, copy, scenarios, test); fixtures/seed/ebp05 and scenarios/EBP-05; AUD-02 composes it under ebp_05; screen-scenarios. Backend additive: participant_name, terminated_on on loans and offsets; detail, code on grid rows; GET /ebp/distributions/test (501).

## Progress log
- 2026-11-06: built. `apps/web/src/screens/EBP-05/EBP-05.test.tsx` written, not run (end pass). tsc and eslint clean.

## Decisions made during this task
DEC-2420
