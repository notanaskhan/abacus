---
id: TASK-6702
title: "T-05-T07: E13 part 1, workpapers/compute/formula.py: closed-grammar tokenizer and parser, typed AST, error codes; no eval"
spec: SPEC-651
acceptance_criteria: [AC-4.5, AC-4.6]
risk_zone: amber
status: in-review
branch: s35-t05-t07
worktree: /Users/ayushkbhatia/Accrued/abacus-s35
created: 2026-11-10
updated: 2026-11-10
plan_key: T-05-T07
---

## Objective
The parser accepts every formula in the TXP-11 and TXP-02 specs, rejects anything outside ADR-237's grammar with a code, and a banned-pattern test proves no eval.

## Plan (amber)
1. `backend/src/abacus/modules/workpapers/compute/` (new compute package): `formula.py` with the
   tokenizer (quoted and bare sheet titles, `$` markers, the handoff's − × ÷ ≠ ≤ ≥), a recursive
   descent parser with a depth bound, frozen AST (`CellRef`, `RangeRef`, `Number`, `Percent`,
   `Negate`, `Binary`, `Compare`, `Call`), `Formula.inputs()` for `formula_inputs`, `render()`.
2. Codes: `syntax`, `ref_invalid`, `unsupported_function`, `type`, plus `cycle` and `div_zero`
   declared for T-05-T08's evaluator. Errors carry code and position only.
3. Gates: import-linter compute contract gains `abacus.modules.workpapers.compute`; banned pattern
   FORMULA-001 (no eval/exec/compile/dynamic import in workpapers/compute and tax/compute).
4. Tests: `backend/tests/unit/workpapers/test_t05t07_formula.py`.
5. Rollback: the package is unused until T-05-T08; revert the commit.

## Progress log
- `2026-11-10` — Built on ADR-237 as proposed (DEC-3016, DEC-3300). A-04's `workpapers/formulas.py`
  (SPEC-308 working papers, errors as values) stays untouched; E13 is a separate grammar for tax
  workbooks. Tests written, not run (end pass).
