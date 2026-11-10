---
id: ADR-237
title: "Workbook formula engine: a closed grammar over firm-authored cells, no eval, client strings stay text in Excel (amends ADR-052 for tax workbooks)"
status: proposed
date: 2026-11-09
deciders: ayushkbhatia  # solo edition; acceptance is his (red ADRs never default on silence)
risk_zone: red
proposal: P-69
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking an ADR, propose a new ADR that supersedes it. Never work around it silently.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

**Status note.** Drafted by T-05-T02 (TASK-6522) from chapter 09 P-69 and DEC-84 as a pre-window
task in S33, for acceptance in S34 (F-02's accept-by Fri Feb 18, 2028) so T-05's formula-engine
rows (T-05-T07, T-05-T08 and after) build from S35. P-69 takes the next free number on `main`.

## Context
ADR-052 treats every client string as hostile, and ADR-110 never evaluates a spreadsheet formula
in an upload. The 1065 numbered workbook (TXP-11) needs formulas: "I18 = F18+G18+H18", a capital
account's crossfoot D + E + F + G + H + I = J, a cell expected to read `='06 Schedule K'!C31 × 25%`.
DEC-84 chose an in-house typed-cell DAG over a library: references and + − × ÷ and SUM, engines
emitting their formulas as provenance, partial re-runs never overwriting human-edited cells, edits
under `expected_version`, reviewers proposing and preparers editing, approvals going stale when an
approved input changes. The workbook also opens in Excel (TXP-11 "Open in Excel"), where a cell
holding a client's text that begins with `=` would otherwise become a formula.

## Decision
1. **Who writes formulas.** Formulas exist only in firm-authored cells: the workbook template the
   firm publishes, and the cells a compute engine fills (which carry the engine's formula as
   provenance). A client value, an imported report's value and an agent's text are always
   values, never formulas, whatever characters they hold.
2. **A closed grammar, parsed, never evaluated.** A formula is parsed by code into an expression
   tree over: decimal literals, cell references (`Sheet!A1`, quoted sheet names, the P-07
   cell-address SPEC's grammar) and ranges, the operators `+ − × ÷` and unary minus, parentheses,
   and the functions `SUM`, `ROUND`, `IF`, `MIN`, `MAX` with comparison operators inside `IF`.
   Anything else answers 422 `formula_invalid` with a code and a position, never the text. There
   is no `eval`, no dynamic import, no host function, no external reference, no volatile function
   and no string function.
3. **A typed-cell DAG.** Cells are typed (decimal, text, date, percent, empty); the engine computes
   in `Decimal` (ADR-050), in topological order, refusing a cycle (`formula_cycle`) and a type
   error (`formula_type`). A recompute never overwrites a human-edited cell (`value_source =
   human`); it marks the cell's dependents and any approval over a changed input stale ("Changed
   after sign-off", "Re-approve…").
4. **Edits.** A preparer's edit goes through `review.api.record_value` with `expected_version`
   (409 `cell_version_conflict` when stale); a reviewer's edit is a proposal routed for approval;
   an agent never edits a cell (it proposes, a person decides; ADR-005).
5. **Open in Excel.** The export writes each firm-authored cell's formula from the DAG and every
   other cell as a value. A text value is written with the text type, so a string starting with
   `=`, `+`, `-` or `@` stays text in Excel (ADR-052); the same data gives the same bytes
   (P-19's deterministic writer).
6. **Scope of the exception.** This amends ADR-052 for firm-authored tax workbook formulas only.
   ADR-110 is unchanged: an uploaded spreadsheet's formulas are never evaluated, and an imported
   workbook's formulas are read as values.

## Options considered
### Option A: an in-house typed-cell DAG over a closed grammar — chosen (DEC-84 b)
- Pros: nothing the grammar does not name can run; Decimal arithmetic; provenance per cell; no
  new dependency.
- Cons: a small grammar; each new function is an ADR-reviewed addition.

### Option B: a spreadsheet formula library (DEC-84 a)
- Why rejected: a library's evaluator accepts far more than the workbook needs (dynamic
  functions, external links), runs on floats, and is a new dependency on a red path.

### Option C: no formulas, values only
- Why rejected: TXP-11's reviewers need to see and check each computed cell's derivation, and
  "Open in Excel" must hand the firm a live workbook.

## Related
ADR-005, ADR-031, ADR-050, ADR-052, ADR-110, ADR-160 (P-07 review grammar and cell addresses),
ADR-320 (P-19 renderer), DEC-84.
