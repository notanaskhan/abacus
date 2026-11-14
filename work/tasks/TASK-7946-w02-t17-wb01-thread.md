---
id: TASK-7946
title: "W-02-T17: WB-01 thread states (discovery, QuestionCard steps, run rows, ChatErrorRow, locked, bubble menu)"
plan_key: W-02-T17
spec: SPEC-653  # W-02 §3.4–§3.7; WB-01 a–e, g
acceptance_criteria: [AC-A3, AC-A4, AC-A5]  # WB-01 a-e and g pass in Vitest with axe clean; locked renders no item or figure
risk_zone: green
status: in-review
branch: w02-t17-wb01-thread
worktree: /Users/ayushkbhatia/Accrued/abacus-s43
created: 2026-11-14
updated: 2026-11-14
---

## Objective
WB-01's thread states on the session snapshot. Finishes W-02-T15's FE notices
(`nothing_written`, `plans_off`) and W-02-T16's thread rendering.

## Plan
- FE: `screens/WB-01/Thread.tsx` (ChatThread binding, QuestionCard above, notices, retry, run
  rows, Edit and resend), `index.tsx` mounts it, `copy.ts`; `domain/workbench` `post` takes
  `answersSeq`/`editsSeq`; kit `ChatThread` gains the bubble menu (`onEditResend`, additive);
  fixtures: the session GET (Hannah's TY2025 session at WB-01 a; the Today session).
- Tests: `apps/web/src/screens/WB-01/WB01.thread.test.tsx`.

## Partial
- WB-01 c's close-run RunCard and d's scheduled-run ApprovalCard slot render as the plan row with
  View run; the full run arc (PlanCard, gathering, results, ApprovalCard) is WB-03's (W-02-T21).
- Axe on each state runs at the S43 end pass.

## Progress log
- 2026-11-14: built; tsc clean (web and ui); tests written, not run (S43 end pass).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-4941 | the thread on ChatThread; notices' words; answers and resends as turns | no |
