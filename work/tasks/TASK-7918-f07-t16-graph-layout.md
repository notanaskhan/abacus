---
id: TASK-7918
title: F-07-T16 T14 GraphCanvasLayout
plan_key: F-07-T16
spec: SPEC-652
acceptance_criteria: [AC-6]  # T14a–c render; last-4 mask only; re-mask after 10 s; Reveal needs the capability
risk_zone: amber
status: in-review
branch: f07-t16-graph-layout
worktree: /Users/ayushkbhatia/Accrued/abacus-s42
created: 2026-11-13
updated: 2026-11-13
---

## Objective
The T14 frame around GraphCanvas: slots, canvas header, dependency banner, list view, the 330
inspector with the masked TIN and Reveal intent, the K-1 band and linked work, single-entity empty.

## Plan
- `packages/ui/src/templates/graph-layout.tsx` (+ test), exported from `templates/index.ts`.

## Partial
- List view draws its own T1 table (IndexList's column model wants a query host); Tier D and
  the gallery page land with the TPL-14 specimen (F-07-T17) and the lock (F-07-T22).
- Closed by S43 (2026-11-14, main 322ca3310): F-07-T22 (#1980): the gallery page and the lock.

## Progress log
- 2026-11-13: built; tests written, not run (S42 end pass).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-4920 | frame, mask rule, reveal intent and re-mask | no |
