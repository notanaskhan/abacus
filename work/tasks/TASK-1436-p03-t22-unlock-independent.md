---
id: TASK-1436
title: Independent AC tests (ADR-078) for password unlock: the sentinel password nowhere outside the request (P-03-T22)
spec: SPEC-322
acceptance_criteria: [AC-31, AC-32, AC-33, AC-34, AC-35]
risk_zone: red
status: in-review
epic: P-03
plan_key: P-03-T22
branch: s11-trust-tests
test_author: ayushkbhatia
test_session: 2026-10-27, branch s11-trust-tests (S11 lane 7; a clean session following .claude/skills/ac-test-author/SKILL.md, from the spec, contracts and ADRs only)
created: 2026-10-27
updated: 2026-10-27
---

## Objective
"A planted sentinel password is found nowhere outside the request, and the evidence version's bytes
and fingerprint are identical before and after unlock."

## Plan (red zone)
- **File:** `backend/tests/integration/backfill/test_p03t22_unlock_independent.py`.
- **Boundary:** `create_app()` over HTTP on the migrated Postgres and the compose S3 image; the
  client upload route and the v7 rendition activities; the outbox delivered through
  `abacus.worker.__main__.publisher()` with a recording Temporal client; error tracking started by
  `configure_error_tracking` with an in-memory Sentry transport; a bucket wrapper that fails every
  write to force a part-way failure.
- **Sinks searched for two sentinels (the right and a wrong password):** responses and headers,
  every log record with its extras, the process's stdout/stderr (the isolated child included),
  every row of every table (text and hex), every object version in the bucket (UTF-8 and UTF-16),
  every outbox payload emitted by the unlock, every workflow start/signal argument, and every event
  error tracking would send.
- **No production change, no migration, flag, matrix or registry edit.** Rollback: delete the file.

## Results (19 tests, all pass)
- AC-31: `password_protected` manifest offering `evidence.unlock`; not offered to the reviewer.
- AC-32: ready with a derivation id and `no-store`; pages, scan run, regions (the 9xx TIN, last4
  3456) and masked rendition all carry that one `derivation_id`; manifest `ready`; the page is a
  PNG. The version row, the stored object versions and the served bytes are identical before and
  after, and sha256 of the upload equals the fingerprint; no new version. `evidence_version.unlocked`
  audited (human, the person) and published once. A second unlock and an unlocked file are 409
  `not_password_protected`.
- AC-33: `{wrong_password, attempts_left: 4}` audited by count only; 4,3,2,1,0 then 429
  `unlock_rate_limited` with `limit` 5 and `retry_after` even for the right password; one
  `unlock_throttled` row; the limit is per person (a colleague still unlocks).
- AC-34: the sentinel sweep above; a part-way storage failure answers 500, reports to error
  tracking without the password and derives nothing; an over-long password and an extra field are
  422 without echo; no password or secret column on the tables the unlock writes.
- AC-35: client admin and reviewer 403 `forbidden`; a wall and another firm 404; flag off 404;
  matrix denies agent, system and client roles and allows only partner, manager, senior, staff with
  independence; `evidence_derivations.created_by_user_id` NOT NULL refuses a machine row.

## Spec drift followed
- C4 §6: a wrong password is 200 `{status: wrong_password}`, not an error.
- DEC-370: refusals are the plain `{"detail": "forbidden"}`.

## Not covered (why)
- "One isolated child": not observable at HTTP; the process-output sweep includes the child.
- Agent context over HTTP: needs a proven run (SYS-001); the matrix and DB layers are proven.

## Progress log
- 2026-10-27: suite written and committed; targeted pass in three `-n 2` runs: 19 passed. No defect found.
