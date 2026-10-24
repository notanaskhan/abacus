---
id: TASK-1034
title: DataTable grammars 3 — grid and leadsheet fields, virtualisation above 200 rows (F-05-T52)
spec: SPEC-048
acceptance_criteria: [AC-3, AC-8]
risk_zone: green
status: done
epic: F-05
plan_key: F-05-T52
branch: s7-f05-t50-t53-ui-kit
created: 2026-10-24
updated: 2026-10-24
---

## Objective
"The grid grammar shows column letters, 34px row numbers and cited cells, and 1,000 fixture rows
keep INP at 200 ms or less with sticky bands."

## Scope
**In**
- `packages/ui/src/data/grid.tsx`: `GridTable`, the grid grammar (C-01 spec 04): column letters
  (A … Z, AA) over 26px, the 34px row-number column, hairs right and bottom, td 27 at 12px, the
  espresso `headerRow`, `cite` ("B4", "Sheet!B4", "D6:D7") lighting rows and exact cells, live
  `<file>!<cell>` match ids from sheet-cell locators with `source`, comment corners with a note,
  column resize (drag, or ← → in 16px steps; minimum 40), ↑ ↓ Home End Enter.
- `DataGrid`: the `leadsheet` grammar (no visible header, rows padding 9 14 at 13px, whole dollars,
  a 52 line-number column, totals 500 over the .22 rule, group bands on band-hd), `rowMatch`, and
  virtualisation at 200 rows and above (`row-window.ts` on @tanstack/react-virtual, fixed grammar
  heights, a scroll viewport, sticky header and group bands, `aria-rowindex` kept). `EvidenceTable`
  takes `grammar="leadsheet"`. The tracing cells move to `match-cells.tsx`.
- `packages/ui/src/data/fields.tsx`: `FieldBlock` and `FieldRow` (C-01 spec 05): min 42 rows, the
  96 to 140 value box, matched (match fill and line; label 500), mismatch (red ink, Flag on), Flag
  and Info ghost buttons shown on hover, flagged or open, Info's source note.
- Specimens `c-01-grid` (Northwind's trial balance workbook from the seed, documents.py),
  `c-01-leadsheet` and `c-01-fields` (the T3 handoff's Feld 2025 Form 1040 lines, `feld-t3.ts`),
  `c-01-virtual` (1,000 fixture rows). Footings: the TB's debits and credits, Feld's lines 9 and 33.
- `e2e/components.spec.ts` "E4 virtualisation": a window in the DOM, the header and a band stuck,
  and the slowest interaction (click, ↓, End, scroll) within 200 ms by the Event Timing API.

**Out**
- The T3 frame that mounts these (F-05-T53). The SheetGrid editing layer (T18).

## Definition of done
- [x] 13 tests in `data/grammars-3.test.tsx`; the E4 virtualisation browser test
- [x] axe harness, INV sweep and white-label sweep over the gallery
- [x] lint, tsc, prettier for `packages/ui` and `apps/web`

## Progress log
- 2026-10-24: built. Decisions in `tokens/DECISIONS.md` (F-05-T52).
