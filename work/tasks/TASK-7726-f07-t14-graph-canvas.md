---
id: TASK-7726
title: F-07-T14 GraphCanvas (SVG)
plan_key: F-07-T14
spec: SPEC-652
acceptance_criteria: [AC-6]  # T14a/T14b geometry; hover darkens only that node's edges; every node reached, selected, moved by keyboard
risk_zone: green
status: in-review
branch: f07-t14-graph-canvas
worktree: /Users/ayushkbhatia/Accrued/abacus-s41
created: 2026-11-13
updated: 2026-11-13
---

## Objective
GraphCanvas (SVG): 180 × 56 nodes, return nodes with state pill, external dashed node, selected
ring, edge styles, hover trace, zoom capsule and Fit, legend, pan, keyboard focus and nudge,
`onLayoutChange` intent.

## Plan
- `packages/ui/src/graph/canvas.tsx` (new), `graph/index.ts`, `graph/canvas.test.tsx`.
- `packages/ui/src/specimens/fixtures/tpl-14.ts`: TPL-14a node faces.
- Rollback: revert; no consumer until GraphCanvasLayout (F-07-T16).

## Partial
- "T14a and T14b pass Tier D": the parity run needs a gallery page, which arrives with
  GraphCanvasLayout and the TPL-14 specimen (F-07-T16, T17) and the lock (T22).
- Hovering an edge rings both ends; the "Since / Source" text needs fields the edge VM does not
  carry yet (T-06's relationships read model).

## Progress log
- 2026-11-13: built; eslint and tsc clean; tests written, not run.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-4729 | canvas structure, intents, keyboard model, TIN backstop | no |
