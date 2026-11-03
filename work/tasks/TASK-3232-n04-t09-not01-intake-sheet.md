---
id: TASK-3232
title: N-04-T09 NOT-01 b, c, d intake sheet
spec: SPEC-000  # row
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: N-04
plan_key: N-04-T09
branch: s26-n04-t09
worktree: /Users/ayushkbhatia/Accrued/abacus-s26
created: 2026-11-03
updated: 2026-11-03
---

# TASK-3232 · N-04-T09 · NOT-01 b, c, d intake sheet (O3 500) in fixture mode

**Epic:** N-04 · **Sprint:** S26 · **Type:** FE · **Zone:** green · **Depends on:** N-04-T05, P-11-T19, F-05-T20 · **Status:** in-review

## Built
- `packages/ui`: `ConfidencePill` (green-tint at 0.95 and above, amber below, percent floored in text, optional note) and `CONFIDENCE_GREEN`; test `confidence-pill.test.tsx`.
- `apps/web/src/screens/NOT-01/IntakeSheet.tsx`: DropZone with a "Choose file…" button; Source; "Extracted by Accrued Agent" with editable fields, ConfidencePill, low-confidence helper and Confirm (PUT with If-Match); Match with a client Picker; Authorization with "Draft Form 2848…"; Assign with the Notify signing partner toggle; Create notice (disabled while extracting, while a low-confidence field is unconfirmed, or without a client) and its toast. TIN shown as last four only.
- "+ Add notice" opens the sheet (no longer drawn disabled); `NoticesIndex`/`NOT01` take `intakeId`.
- Fixtures `seed/notice-intake.ts` (Santos CP14), scenarios b, c, d; test `IntakeSheet.test.tsx`.

## Partial
- The composed duplicate, manual-entry and no-client states are not drawn yet.
- "Draft Form 2848…" does not open SIG-02 yet; the Assign card has no assignee picker (the creator is the assignee unless the intake names one).

## Progress log
- 2026-11-03: built; tsc and eslint clean; vitest not run (end pass).
