---
id: TASK-8017
title: "T-07-T03: protected bundle: tax.yaml fiduciary and estate actions, three flags, gate kinds, notification kinds, error codes"
spec: SPEC-656
acceptance_criteria: []
risk_zone: red
status: in-review
branch: t07-t03-protected-bundle
worktree: /Users/ayushkbhatia/Accrued/abacus-s44
created: 2026-11-14
updated: 2026-11-14
plan_key: T-07-T03
---

## Objective
protected bundle: tax.yaml fiduciary and estate actions, three flags, gate kinds, notification kinds, error codes.

## Plan
Files: `docs/architecture/permission-matrix/tax.yaml` (epic §4.4 rows), `docs/architecture/feature-flags/tax.yaml` (three flags, 2026-11-14 → 2027-05-13, DEC-137), notification catalogue (two kinds), C13 gate kinds (three), error codes (§4.3 list) through the error-code generator; `make regenerate`. Registry TABLE_OWNERS land with T07's tables (schema_check fails a listed table that does not exist). Tests: `tests/unit/tax/test_t07t03_protected_bundle.py` (agent deny on every write; portal deny; flags default off). Rollback: revert the commit and regenerate.

## Progress log
- `2026-11-14` — Built. Fifteen tax.yaml actions, three flags, regenerated `_matrix.py`, `_flags.py`, `actions.gen.ts` and the generated matrix test; `tests/unit/tax/test_t07t03_protected_bundle.py` (not run; end pass).
- **Partials.** C13 gate kinds (`instrument_interpretation_approval`, `fiduciary_computation_sign_off`, `estate_values_approval`) and notification kinds (`instrument_interpretation_ready`, `instrument_read_finished`) register with a service function, so they land with T12, T16 and T22. TABLE_OWNERS land with T07. Error codes land with T05's exception classes (the catalogue is generated from raisers).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
