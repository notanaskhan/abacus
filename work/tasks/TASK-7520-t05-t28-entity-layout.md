---
id: TASK-7520
title: T-05-T28 EntityReturnLayout route subtree and form-family dispatch
plan_key: T-05-T28
spec: SPEC-000  # T-05 §5.1, F1
acceptance_criteria: [AC-1]  # a 1065 opens on Agent while a 1040 opens TAX-02; every Group B slug outside the form redirects to the default tab
risk_zone: green
status: in-review
branch: t05-t28-entity-layout
worktree: /Users/ayushkbhatia/Accrued/abacus-s39
created: 2026-11-12
updated: 2026-11-12
---

## Objective
The entity return's route subtree: dispatch `/tax-returns/$returnId` by form family, Group A and
Group B tabs with P1 tabs planned, the subbar (Checkpoints, sync chip, state pill, Assistant), slug
validation before load.

## Plan
- `apps/web/src/domain/tax/entityReturn.ts` (+ test): forms, Group A/B, P1 set, labels, screens,
  `sectionOf` (validation), `slugOf`.
- `apps/web/src/screens/TXP-00/EntityReturnLayout.tsx`: T-02's `RecordHeader` (Checkpoints, sync
  "Not yet exported", state, Assistant) and the two Segmented tracks; P1 review tabs absent in
  production, "Not built yet" where planned screens show.
- `apps/web/src/routes/firm/tax-returns.tsx`: `/tax-returns/$returnId` dispatches (1065 with
  `tax.entity_workspace` → entity layout on Agent; otherwise TAX-02 as today), `/issues`,
  `/workpaper`, `/activity`, `/review/$review` (beforeLoad redirects an invalid slug to Agent).

## Partial
- The section screens (TXP-00 is T-05-T29; TXP-10, TXP-11, TXP-01, TXP-02, TXP-05, TXP-07 later
  rows) show the planned state inside the frame; manifest entries move from `planned` with them.

## Progress log
- `2026-11-12` — Built (DEC-4520). Tests run at the S39 end pass.
