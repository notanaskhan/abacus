---
id: TASK-3027
title: A-04-T21 AUD-05 narrative workpaper screen
spec: SPEC-620
acceptance_criteria: [AC-11, AC-12, AC-13]
risk_zone: green
status: done
epic: A-04
plan_key: A-04-T21
branch: s25-a04-t21 (stacked on s25-a04-t20)
worktree: /Users/ayushkbhatia/Accrued/abacus-s25
created: 2026-11-02
updated: 2026-11-02
---

## Objective
"AUD-05 a-e render at Tier C, Approve minutes is absent for Marcus, and Escalate opens SHL-14
prefilled without sending anything."

## Built
- `apps/web/src/screens/AUD-05/` (Narrative, copy, index, scenarios, test); route
  `/audits/$auditId/narrative/$wpRef`; manifest path; `fixtures/seed/aud05.ts`,
  `fixtures/scenarios/AUD-05.ts`.
- Test: `screens/AUD-05/AUD-05.test.tsx` (6, pass).

## Progress log
- 2026-11-02: built. Partial (DEC-2074): decision strip, SHL-07 guidance popover, amber notes on
  unflagged rows, inquiries list.

## Decisions made during this task
DEC-2074.
