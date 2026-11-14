---
id: TASK-7943
title: "I-02-T17: Today drill-in, assign, history and ask (SHL-23 2, 3; HOME-05 b)"
plan_key: I-02-T17
spec: SPEC-654 (I-02 §3.5–§3.8)
acceptance_criteria: [AC]  # the to-do by Create; Basis reserved; the 9:26 answer's three chips
risk_zone: green
status: in-review
branch: i02-t17-today-drill
worktree: /Users/ayushkbhatia/Accrued/abacus-s43
created: 2026-11-14
updated: 2026-11-14
---

## Objective
Drill-in with ‹ Today, narrative, blockers, Waiting downstream and Open return ›; Assign open
items through SHL-17 prefills; History and a read-only past brief; Rebuild; the composer and the
cited answer card. Finishes I-02-T15/T16's partials (drill-in, history, ask).

## Plan
- FE: `screens/SHL-23/drill.tsx` (TodayDrill, AssignSheet, TodayHistory, AskThread), `live.tsx`
  (the views), `index.tsx` (onDrill, thread, readOnlyLine; High risk actions), `copy.ts`;
  `domain/today` hooks; HOME-05 dock and drawer draw `TodayPaneLive`; fixtures: the Today
  session (SHL-23 3) and its GET.
- BE: history and past brief live (`practice/today/assembly.py`, `routes.py`; agents
  `briefing_snapshots_of`/`briefing_snapshot_of`); the composer's availability; High risk refs to
  work items; `SessionItemKind` widened (additive). Client regenerated.
- Tests: `apps/web/src/screens/SHL-23/SHL23.drill.test.tsx`.

## Partial
- The saved-prompt chip stays hidden until W-03 (as planned).
- Tier D and axe for these states are I-02-T21's.

## Progress log
- 2026-11-14: built; tsc clean on the touched files; tests written, not run (S43 end pass).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-4938 | one container; prefills by Create only; history over user snapshots; item kinds | no |
