---
id: TASK-1349
title: Independent AC tests (ADR-078) for the single intake commit, second session (P-07-T44)
spec: SPEC-332
acceptance_criteria: [AC-23]
risk_zone: amber
status: in-review
epic: P-07
plan_key: P-07-T44
branch: s10c-tests
test_author: ayushkbhatia
test_session: 2026-10-27, branch s10c-tests (separate from P-07-T42's; TASK-1324's suite was written in T42's branch)
created: 2026-10-27
updated: 2026-10-27
---

## Objective
Atomicity, `Idempotency-Key` replay, Prospect-only creation under `client.intake`, the conflict
check before commit, estate validation and the SSN guard, for P-07-T42 (#438).

## Plan (amber)
- **File (tests only):** `backend/tests/integration/backfill/test_p07t44_intake_adr078.py`.
- **Sources only:** `docs/contracts/intake-import.md` (§1 "Live intake", §2, §6, §7), the
  organisations matrix, DEC-43, DEC-430, DEC-441, the P-07-T44 row.
- **Coverage:** a commit refused inside its unit of work leaves nothing and the draft
  committable; the key before anything else; same key other body; a second key on a committed
  draft; concurrent commits; updates after commit refused; another person's draft, another
  firm's and a walled client 404 (INV-2, INV-3); a renamed draft needs a new check; Prospect
  only; agent and system refused; the guard on autosave; dedupe never names a walled client.
- **Rollback:** delete the file.

## Progress log
- 2026-10-27: planned and written.
- 2026-10-27: targeted pass: 20 passed, 1 strict xfail. The date of death is reported on the services step; the guard test uses an ITIN-form 9xx fake (912-70-1234). Defect: ED-116 (racing commits of one draft answer 500; one estate written) held by `test_ac_a_losing_concurrent_commit_answers_the_result_or_409_never_500`, three races per run. Helper renamed `commit_intake` (UOW-001).
