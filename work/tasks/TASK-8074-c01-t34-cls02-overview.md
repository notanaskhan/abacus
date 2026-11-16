---
id: TASK-8074
title: "C-01-T34: CLS-02 Overview states a-e on T2 without dock"
spec: SPEC-655
acceptance_criteria: [AC-28, AC-29, AC-30, AC-31]
risk_zone: green
status: in-review
branch: c01-t34-cls02-overview
worktree: /Users/ayushkbhatia/Accrued/abacus-s46
created: 2026-11-15
updated: 2026-11-15
plan_key: C-01-T34
---

## Objective
CLS-02's Overview body inside the close shell: the Summary rail and the close run (RunCard, run
history, task groups, decision card, failed task, composer) over the generated client, with
fixture scenarios for the handoff's frames A to E.

## Built
- `screens/CLS-02/Overview.tsx`, `overview-copy.ts` (verbatim handoff words), exported from the
  screen's index; `routes/firm/closes.tsx` renders it as the Overview tab's body.
- `fixtures/scenarios/CLS-02.ts`: `overview-a` to `overview-e` from the C-01-T13 figure book.
- `screens/CLS-02/CLS-02.overview.test.tsx` (6 tests; with the shell's, 9 pass locally).
- The API client regenerated (`make generate`) for the S46 contract changes so far.

## Progress log
- `2026-11-15` — Built; vitest and `tsc` clean for the screen. Tier C parity and axe run at the end
  pass. The revision's Board (F, G) is K-04's ENG-10 close variant, not this row.
- The run's live wiring is in place (the same endpoints C-01-T20 serves); the C-01-T42 live swap
  turns it on against a stack.
