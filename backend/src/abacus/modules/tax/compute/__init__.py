"""Pure computation for tax: no clock, no database, no I/O (ADR-050).

- `transcripts`: IRS transcript parsing and the comparison with the return as filed (T-01-T45).
- `payments`: extension safe harbors, required annual estimated-tax payments and installments
  (T-03-T04), with the engine parameters in `parameters/ty<year>.yaml` (PROTECTED, DEC-76).
- `likely_to_extend`: TAX-13 c's signals (T-03-T04).

This package imports only `abacus.kernel.numeric`, `abacus.kernel.calendar` and itself (the
import-linter compute contract).
"""
