---
id: TASK-2509
title: F-06-T19 calc tree beside the source-workbook grid (T6e), variance explanation slot
spec: SPEC-400
acceptance_criteria: [AC-31]
risk_zone: green
status: in-review
epic: F-06
plan_key: F-06-T19
branch: s20-f06-t19
created: 2026-10-30
updated: 2026-10-30
---

## Objective
Story 5.6: the calculation traced to the source workbook. Hover or focus a calc step and its
Sheet!Cell lights in the grid within 360 ms; Enter pins, Escape clears and returns focus; every
variance state in words and icons.

## Plan (green)
- `packages/ui/src/data/CalcTree.tsx`: `role="tree"`, `treeitem` with `aria-level`, a 0.5px rail
  per level, op glyph, label, source ref (match ink while lit), server value (negatives red, "—"
  ink-4); `useMatch` on steps with a typed match id; Enter pins; arrows/Home/End move focus.
- `WorkbookLayout`: renders `calc` (`CalcPane`) and `grid` (`GridPane`: `GridTable` with
  `source`/`sheet`, file icon header, 30h "Sheet!Cell value · meta" footer) panes inside one
  `MatchScope`; `GridPayload` type exported.
- `VarianceCell`: optional `explanation` slot for the O1 note (the consumer renders an agent's
  note through AgentText).
- T6 board: Calculation view enabled; state e (Calder Family Trust's ending capital: nine steps,
  match ids from `matchIdOf({kind: "sheet_cell", …})`; the workbook rows as drawn).
- `/components/c/c-01-calc-tree` specimen on the Northwind trial balance.
- Rollback: revert; additive.

## Acceptance
| Check | Test |
|---|---|
| Tree semantics, rails | `packages/ui/src/data/CalcTree.test.tsx` |
| Hover/focus lights the cell (360 ms fade), Enter pins, Escape clears | same |
| A form-line step lights nothing (INV-2) | same |
| Five variance states in words and icons; explanation slot | same |

## Progress log
- 2026-10-30: built (tests first, run at the end review). DEC-1558.
