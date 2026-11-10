---
id: TASK-3025
title: A-06-T12 Evaluation chrome and wiring
spec: SPEC-642
acceptance_criteria: [AC-3]
risk_zone: green
status: done
epic: A-06
plan_key: A-06-T12
branch: s25-a06-t12 (stacked on s25-a05-t17)
worktree: /Users/ayushkbhatia/Accrued/abacus-s25
created: 2026-11-02
updated: 2026-11-02
---

## Objective
"All four routes render in fixture mode with tab counts from the server, Back closes each new
overlay, and planned links render Not built yet in fixture builds and nothing in production."

## Built
- `apps/web/src/screens/evaluation/` (EvaluationPage, EvaluationTabs, PlannedSheet, copy, index,
  test); four routes in `routes/firm/audits.tsx`; `routes/firm/evaluation.tsx` (overlay keys);
  manifest paths for AUD-15, AUD-16, AUD-17, AUD-20; audit fixture handlers for the counts.
- Test: `screens/evaluation/evaluation.test.tsx` (9, pass).

## Progress log
- 2026-11-02: built. The four screens' own bodies land with A-06's screen rows.

## Decisions made during this task
DEC-2072.
