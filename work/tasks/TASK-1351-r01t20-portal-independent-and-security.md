---
id: TASK-1351
title: ADR-078 independent AC tests for R-01-T07, T08, T11, T13 and the portal security cases (R-01-T20)
spec: SPEC-323
acceptance_criteria: [AC-3, AC-4]
risk_zone: red
status: in-review
epic: R-01
plan_key: R-01-T20
branch: s10c-tests
test_author: ayushkbhatia
test_session: 2026-10-27, branch s10c-tests (written from C5 `portal-pbc`, not from the read models)
created: 2026-10-27
updated: 2026-10-27
---

## Objective
"The suites pass from the contract alone, the security file fails on a planted cross-scope
read, and TASK-061 is recorded closed."

## Plan (red)
- **Security cases** appended to `backend/tests/security/test_portal_scope_isolation.py`: room
  isolation, forged binder and request ids (one answer), contributor scope, closed binders,
  tax delegation without consent, and a planted cross-scope room read the judgement catches.
- **AC suite** `backend/tests/security/test_r01t20_portal_pbc_independent.py` over portal
  sessions minted through the pre-session routes: T07 (client words, footing counts, closed
  vocabulary, no firm code or amount, contributor scope), T08 (ignore note as a shared comment,
  undo, `nothing_to_undo`, `firm_already_acted` after a waive, mark-done undo, replay), T13
  (room exactly the delegated requests, n of N, suggest by words, fail closed without consent,
  no room for a full-client person), T11 (blocked, TASK-1221 / DEC-348: a strict xfail).
- **Sources only:** `docs/contracts/portal-pbc.md`, `docs/screens/POR-03.md`, `POR-04.md`,
  `POR-14.md`, DEC-240, DEC-333, DEC-334, DEC-387, DEC-388.
- **TASK-061:** recorded closed by this suite (its progress log), per R-01 §10.3.3.
- **Rollback:** revert the commit.

## Progress log
- 2026-10-27: planned.
- 2026-10-27: built and passed: the AC suite and the six security cases (one planted-read judgement). Binders are seeded as part 2 (the site's list holds pbc part 1). Defect: ED-118 (a closed binder reads read-only but the client write routes accept an Ignore and an upload intent) held by a strict xfail; the read half passes. R-01-T11 stays a strict xfail on TASK-1221 (DEC-348). TASK-061 recorded closed by this suite (DEC-448).
