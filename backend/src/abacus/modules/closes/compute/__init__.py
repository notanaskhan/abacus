"""The closes compute package (C-01 §0 "the code-first engine"; ADR-050).

Pure functions over typed inputs: Decimal only, no clock, no database, no I/O. It imports only
`abacus.kernel.numeric` and `abacus.kernel.calendar` (the import-linter contract in
`backend/pyproject.toml`). `reconciliation.py` is the two-sided bank reconciliation (C-01-T22).
"""
