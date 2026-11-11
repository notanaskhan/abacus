---
id: TASK-6814
title: "T-05-T12: Promote the AUD-09 spreadsheet grid (A-04) to packages/ui WorkbookGrid: column letters, row numbers, hairlines, selected cell, comment corner, cited and proposed cells, name box, formula bar, sheet tabs with the open-issue dot, Sheet!Cell footer, keyboard model, virtualisation above 200 rows; gallery specimen"
spec: SPEC-651
acceptance_criteria: [AC-4.1, AC-4.3]
risk_zone: green
status: in-review
branch: s36-t05-t12
worktree: /Users/ayushkbhatia/Accrued/abacus-s36
created: 2026-11-11
updated: 2026-11-11
plan_key: T-05-T12
---

## Objective
The specimen passes axe and the keyboard suite, and AUD-09 and EBP-09 render unchanged on the
promoted component.

## Built
`packages/ui/src/data/workbook-grid.tsx` (exported from `@abacus/ui`): the grid grammar's letters,
row numbers and hairlines (reusing `columnLetter`, `citedCells` and the E4 row window), one selected
cell (match tint with an inset ring), cited cells, Proposed micro pills, comment corners, name box,
formula bar ("(empty) — expected …" for an empty cell a tie-out names), sheet tabs with the amber
open-issue dot, the "Sheet!Cell" footer, the keyboard model (arrows, Enter or F2 to edit, Enter to
commit to the host, Esc to cancel), virtualisation above 200 rows. Gallery specimen
`c-01-workbook-grid` on TXP-11 A's cells. Test `data/workbook-grid.test.tsx`.

## Progress log
- `2026-11-11` — Built (S36). Tests written, not run (end pass); axe on the specimen runs with the
  gallery suite at the end pass.

## Partials
- AUD-09 and EBP-09 render their own sheet tables today (no shared grid component to swap), so
  they are unchanged by construction; moving them onto WorkbookGrid is left to their next row so
  their locked parity frames are not disturbed this sprint.
