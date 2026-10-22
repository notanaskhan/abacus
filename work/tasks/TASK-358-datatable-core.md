---
id: TASK-358
title: E4 DataTable core — headless model on react-table, ledger and statement grammars, MoneyCell, TickCell, PropChip, grid semantics, server totals only (F-05-T27)
spec: SPEC-048
acceptance_criteria: [AC-8]
risk_zone: green
status: done
epic: F-05
plan_key: F-05-T27
branch: f05-t27-datatable
created: 2026-10-22
updated: 2026-10-22
---

## Objective
"The ledger grammar renders 30px rows with cents, the arrow and Enter keyboard model and
role=grid, and no code path sums a column in the browser."

## Scope
**In**
- `packages/ui/src/data/`: `types.ts` (the E4 row payload: `{id, kind, label, indent, tag, cells}`
  with decimal strings), `cells.tsx` (`MoneyCell` through format.ts, `TickCell`, `PropChip`),
  `data-grid.tsx` (`DataGrid` on `@tanstack/react-table` v9 `useTable`, `ledger` and `statement`
  grammars, role=grid with `aria-activedescendant`, ↑↓/Home/End/Enter/double click).
- C-01 specimens: the kit's bank reconciliation (ledger) and Schedule L (statement).

**Out**
- Evidence, grid and leadsheet grammars, VarianceCell, CommentCorner, CitedCell and AccountTree:
  with the screens that need them. Virtualisation above about 200 rows: with the first such screen.
- Replacing the TASK-101 `DataTable` in its eight callers: F-05-T28 (IndexList).

## Definition of done
- [x] 12 acceptance tests in `data/data-grid.test.tsx`
- [x] axe, keyboard and target-size harness (F-05-T24) clean over the new specimens
- [x] `make check-fast`

## Progress log
- 2026-10-22: built on react-table 9.3.1 (`useTable`, `tableFeatures({})`; the core row model is
  built in).
