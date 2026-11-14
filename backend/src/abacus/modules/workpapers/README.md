# workpapers

Zone: amber. Pre-registered by F-03-T08 (ADR-140); empty until its first epic.

Will own (docs/plan/03-backend-architecture.md §2.2): Workpapers, sections, versions and cells; sheets, columns, rows, cells and views; agent columns; procedures; leadsheets; tie-out checks; test attribute results; the formula DAG.

## Adding to the planning workpapers (A-04-T39)
A reviewable registers with `review.api.register_reviewable`, a suggestion target with its applier in
`agents`, an exception route with `assurance`'s route registry, and a section kind in the methodology
pack (never here). Operating notes: `docs/operations/audit-planning/README.md`.

## EBP modes (A-05; A-05-T62)
The section drafter's EBP modes (`ebp_trust`, `ebp_form5500`, `related_parties`, ...) live in `assurance/*_mode.py` and register their mappings with `agents.section_sources`. They read masked pages and code's numbers as facts and propose only (C3 suggestions; no tools). They stay synthetic-only until A-05-T63's clearance. Runbook: `docs/runbooks/ebp-modules.md`.

## The workbook formula engine, E13 (T-05-T07, T08; ADR-237; T-05-T71)
`compute/formula.py` and `compute/dag.py` are pure (no clock, database, I/O or `eval`; a
banned-pattern test reads both). A workbook formula is parsed by code into a typed tree, never
evaluated as text.
- **Grammar (closed, ADR-237 §2).** Numbers, cell references (`C31`, `Sheet!A1`,
  `'06 Schedule K'!C31`, ranges inside one sheet), `+ - * /`, unary minus, `%`, comparisons only as
  `IF`'s condition, and five functions: `SUM`, `ROUND`, `IF`, `MIN`, `MAX`. Anything else is a
  `FormulaError` with a code (`syntax`, `ref_invalid`, `unsupported_function`, `type`) and a
  character position, never the formula text (422 `formula_invalid`).
- **Graph and order.** Each formula cell depends on every address it reads (a range is each cell
  in it); a cell nobody wrote reads 0. A cycle is refused before evaluation (`cycle`, naming the
  addresses in order). Evaluation order is a deterministic topological order (sheet order, then
  row, then column among ready cells).
- **Arithmetic.** Exact `Decimal` in `kernel.numeric`'s context; `ROUND(x, n)` rounds half up; a
  division by zero makes the cell and every reader `div_zero`, and nothing raises.
- **Dirty set.** An edit recomputes only its dependents, transitively, in evaluation order. The tax
  module bounds a synchronous edit at 500 dependents (`tax/cell_edit.py`, `recompute_too_large`);
  a larger fan-out is a run.
- **Provenance.** A computed cell records its formula as `formula.render` writes it back and its
  inputs' canonical addresses, so SHL-09 can say how a figure was made. The xlsx renderer
  (`render_workbook`) writes the same closed-grammar formulas and client strings as text.
- **Changing it.** A new function or operator is an ADR-237 amendment, a grammar test and a golden
  case first; never a widening in code alone. The operating runbook is
  `docs/runbooks/entity-return-workbook.md`.

