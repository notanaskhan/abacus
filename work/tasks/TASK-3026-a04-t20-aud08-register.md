---
id: TASK-3026
title: A-04-T20 AUD-08 risk register screen
spec: SPEC-620
acceptance_criteria: [AC-19, AC-20]
risk_zone: green
status: in-review
epic: A-04
plan_key: A-04-T20
branch: s25-a04-t20 (stacked on s25-a06-t12)
worktree: /Users/ayushkbhatia/Accrued/abacus-s25
created: 2026-11-02
updated: 2026-11-02
---

## Objective
"AUD-08 a, b, b2 and d render at Tier C, the Unaddressed tally filters to R8, and only Margaret
sees the approve controls."

## Built
- `apps/web/src/screens/AUD-08/` (Register, RiskDrawer, index with the drawer host, copy,
  scenarios, test); route `/audits/$auditId/risks`; overlay `?ov=risk:<code>`
  (`routes/firm/risks.tsx`); manifest path; `fixtures/seed/aud08.ts`, `fixtures/scenarios/AUD-08.ts`.
- Test: `screens/AUD-08/AUD-08.test.tsx` (5, pass).

## Progress log
- 2026-11-02: built. Not here: Remind's SHL-14 prefill and the Tier C parity run (A-04-T38).

## Decisions made during this task
DEC-2073.
