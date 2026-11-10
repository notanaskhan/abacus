---
id: TASK-3024
title: A-05-T17 EBP-02 screen
spec: SPEC-640
acceptance_criteria: [AC-15]
risk_zone: green
status: done
epic: A-05
plan_key: A-05-T17
branch: s25-a05-t17 (stacked on s25-a05-t21)
worktree: /Users/ayushkbhatia/Accrued/abacus-s25
created: 2026-11-02
updated: 2026-11-02
---

## Objective
"Hovering a provision lights the same line in the viewer, 'Citations (20)' equals the row count,
and Sign off stays disabled until every row is verified."

## Built
- Contract: `PlanReviewOut.workpaper_id`, `.sign_offs`; `ProvisionOut.reference`, `.cell`,
  `.value_hash`; `review.FieldState.content_hash`; `EbpImportOut` rename; client regenerated.
- `apps/web/src/screens/EBP-02/` (Provisions canvas, copy, artboard, scenarios, test);
  `fixtures/seed/ebp02.ts`, `fixtures/scenarios/EBP-02.ts`; AUD-02 opens it on `ebp_02`.
- Test: `screens/EBP-02/EBP-02.test.tsx` (8, pass).

## Progress log
- 2026-11-02: built. Partial: the viewer's line lighting (DV-EBP-02-3) and SHL-07 on the
  reference, SHL-15 from the conflict, SHL-12 from Sign off… (the hosts open them by route).

## Decisions made during this task
DEC-2071.
