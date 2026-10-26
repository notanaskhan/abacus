---
id: TASK-1324
title: Independent AC tests (ADR-078) for the single intake commit (P-07-T44)
spec: SPEC-332
acceptance_criteria: [AC-23]
risk_zone: amber
status: in-review
epic: P-07
plan_key: P-07-T44
branch: s10b-client-intake
created: 2026-10-26
updated: 2026-10-26
---

## Objective
"The suite is committed before T42 opens for review and passes unchanged." Atomicity,
Idempotency-Key replay, Prospect-only creation under `client.intake`, a cleared conflict check
before commit, estate validation (date of death for Form 706) and the SSN guard on real tenants,
for P-07-T42 (TASK-1326).

## Plan
- **File** `backend/tests/integration/backfill/test_p07t44_intake_commit_independent.py`, written
  from P-07 §3.3 Story 3.1, §4.2 M8, §4.3, `docs/contracts/intake-import.md` and DEC-374 before
  T42's code. HTTP through `create_app()` behind `clients.v2` (and `engagements.v2`,
  `engagements.acceptance_v2` for the conflict check and the acceptance record).
- Committed first as a module-level strict xfail citing TASK-1324 (DEC-399); T42's commit drops
  only that marker, and the tests then pass unchanged.
- **Spec gaps** are named in the module docstring (the TIN is not an intake field, DEC-374; the
  SSN guard reads the draft's text fields; the conflict check names the draft as its subject).
- No migration, flag or matrix edit. **Rollback**: delete the file.

## Progress log
- 2026-10-26: planned and written as strict xfails before T42.
- 2026-10-26: T42 landed; the module marker was dropped and the 12 tests pass. One helper rename
  after the gates: `World.commit` became `World.commit_intake` (banned pattern UOW-001 reads any
  `.commit(` as a unit-of-work bypass); no assertion changed.
