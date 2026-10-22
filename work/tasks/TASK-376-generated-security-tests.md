---
id: TASK-376
title: Generated security tests part 1 - tenant isolation and the permission matrix (Q-02-T13)
spec: SPEC-025
acceptance_criteria: [AC-7]
risk_zone: red
status: done
epic: Q-02
plan_key: Q-02-T13
branch: q02-t13-generated-security
created: 2026-10-22
updated: 2026-10-22
---

## Objective
"Both generators run in stage 2, a seeded cross-tenant read fails the isolation test, and a hand
edit to a generated file fails check-generated." (ADR-080)

## Plan (red)
- `abacus_tools/codegen/security_tests.py` renders `tests/security/test_tenant_isolation.py` (one
  case per tenant-scoped table in the registries: RLS on, forced, keyed to `app.tenant_id`, and
  nothing of firm B's read under firm A) and `tests/security/test_permission_matrix_generated.py`
  (every action x human role, allow or deny as the matrix states, conditions included: an allow
  needing level, function, offshore, attest or gate facts denies without them; `scope_only`
  denies a client role without a grant). Added to `GENERATORS` (check-generated, regenerate).
- Hand-written: `tests/security/isolation.py` (the per-table check), `matrix_harness.py` (every
  layer but the matrix satisfied), `support.two_firms` (seeded once per database).
- Meta-tests: `test_isolation_detects.py` (RLS switched off on a private database is reported,
  with the leaked rows), `tests/unit/tools/test_security_tests_codegen.py` (a hand edit fails).
- Rollback: revert.

## Definition of done
- [x] 144 isolation cases and 2,072 matrix cases pass
- [x] Meta-tests pass
- [x] `make check-fast`

## Note for anyone adding a table or a matrix row
`make regenerate` rebuilds these files; `make check-generated` fails until you do.

## Progress log
- 2026-10-22: built in one session.
