---
id: TASK-7920
title: F-07-T18 T17 FormRendererLayout
plan_key: F-07-T18
spec: SPEC-652
acceptance_criteria: [AC-6]  # no editable control; Go to lights the field; total shows the server's tie state
risk_zone: amber
status: in-review
branch: f07-t18-form-renderer
worktree: /Users/ayushkbhatia/Accrued/abacus-s42
created: 2026-11-13
updated: 2026-11-13
---

## Objective
T17: Workbook/Form toggle, thumbnails 120, the form face on the E5 SourceViewer (capsules,
Download only in ⋯, Show traces), the right 330 pane with K-1s, Total = Schedule K and
diagnostics; loading.

## Plan
- `packages/ui/src/templates/form-renderer.tsx` (+ test), exported from `templates/index.ts`.

## Partial
- Tier D parity of T17a/T17b runs with the TPL-17 specimen (F-07-T19, S43) and the lock
  (F-07-T22); the FieldLayer is the viewer's region layer (no separate component).
- Closed by S43 (2026-11-14, main 322ca3310): F-07-T19 (#1978) and F-07-T22 (#1980): the TPL-17 specimen and T17 parity.

## Progress log
- 2026-11-13: built; tests written, not run (S42 end pass).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-4921 | viewer pipeline, match-lit Go to, server tie state | no |
