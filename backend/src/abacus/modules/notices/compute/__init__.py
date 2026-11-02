"""The notices compute library (N-04-T04; N-04 §4.4; ADR-050: code computes, models judge).

Pure: no clock, no database, no I/O beyond reading its own parameter files, and no import of any
module; it imports only `abacus.kernel.numeric` and `abacus.kernel.calendar` (the import-linter
contract in `backend/pyproject.toml`). Money is `Decimal` under the kernel's context with explicit
half-up rounding to cents. Every result carries a `Stamp` (`engine_name`, `engine_version`, the
SHA-256 `inputs_hash` of its canonical inputs), so the same inputs never make a new version.

- `notice_types.lookup(code)`: the catalogue in `notice_types.yaml` (PROTECTED).
- `risk.band(respond_by, as_of)`: red within 7 days, amber within 30, otherwise none.
- `plausibility.respond_by(...)`: the respond-by against the type's window; never corrects it.
- `underreporter.compare(...)`: notice vs return as filed vs information returns, by code.
- `bracket.check(...)`: the agency's tax change under the year's ordinary schedule (QN-3).
- `balance_due.compare(...)`: the notice's balance against the return's tax and payments.
- `payments.foot(...)`: tax + interest + penalty = total; the notice's figures, never recomputed.
- `clocks.follow_up_on(sent_on, days)`: calendar days, never rolled (K-02 I-CLOCKS).
"""
