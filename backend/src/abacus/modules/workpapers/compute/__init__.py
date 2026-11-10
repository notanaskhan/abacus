"""E13, the tax workbook's formula engine (T-05 §4.4; ADR-237, P-69, DEC-84).

A compute package: pure functions over typed inputs, importing only `abacus.kernel.numeric` and
`abacus.kernel.calendar` (the import-linter contract in `backend/pyproject.toml`). Part 1 is
`formula.py` (the closed grammar: tokenizer, parser, typed AST); part 2 adds `dag.py` and
`tieouts.py` (T-05-T08).
"""
