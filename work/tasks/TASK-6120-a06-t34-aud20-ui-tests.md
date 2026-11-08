---
id: TASK-6120
title: "A-06-T34 independent tests for the AUD-20 UI, and N/A asks for its reason first"
spec: SPEC-000  # row (A-06-T34)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: A-06
plan_key: A-06-T34
branch: s30-a06-t34
worktree: /Users/ayushkbhatia/Accrued/abacus-s30
created: 2026-11-08
updated: 2026-11-08
---

## Objective
ADR-078 tests for A-06-T30: client preview never shows checklist, sources, agent text or studio links; LinkedValueChip renders server values only; checklist N/A requires a reason; Send draft needs the explicit human click.

## Plan
- `apps/web/src/screens/AUD-20/A06T34.test.tsx`: preview (d) has the watermark and no checklist, sources, figure buttons, agent text or studio links; a source scan of `Statements.tsx` finds no arithmetic on amounts; choosing N/A with no reason opens the reason field and sends nothing; opening the send sheet (a2) sends nothing.
- Fix found by the test: `Statements.tsx`'s checklist row sent N/A with an empty reason (the server answers 422 `reason_required`); it now asks for the reason first.

## Progress log
- 2026-11-08: built. Written, not run (tests at the end review). tsc shows no errors in AUD-20; eslint and prettier clean.

## Decisions made during this task
None.
