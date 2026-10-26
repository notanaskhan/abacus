---
id: TASK-1348
title: Independent AC tests (ADR-078) for independence live, second session (P-07-T43)
spec: SPEC-332
acceptance_criteria: [AC-17, AC-18, AC-19, AC-20, AC-21, AC-22, AC-27, AC-28]
risk_zone: amber
status: in-review
epic: P-07
plan_key: P-07-T43
branch: s10c-tests
test_author: ayushkbhatia
test_session: 2026-10-27, branch s10c-tests (a session separate from P-07-T41's; TASK-1323's suite was written in T41's branch)
created: 2026-10-27
updated: 2026-10-27
---

## Objective
Self-only confirmation, the sealed decline note read only as the contract says, the conclusion
EP-only with fresh MFA and its preconditions (INV-1), breach events insert-only, rotation
derivation, G2 provider and attest-only scope, for P-07-T41 (#437).

## Plan (amber)
- **File (tests only):** `backend/tests/integration/backfill/test_p07t43_independence_adr078.py`,
  beside TASK-1323's suite and not sharing its helpers.
- **Sources only:** `docs/contracts/acceptance-independence.md` (§1 "Independence as built", §2,
  §5, §6, §7), the engagements matrix, DEC-428, DEC-429, the P-07-T43 row.
- **Coverage:** the caller's own confirmation even with another person's id in the body; the
  decline note sealed and read only by the person and the conclude holder; reminders by a person;
  the conclusion EP-only, partner level, fresh MFA, one count per blocker, a breach not blocking
  it but G2; the supersede chain; breach events once each and insert-only for the app role; NAS
  rules (attest only, SKE designee, the EP's decision locked, service codes); rotation without a
  gap; walls (INV-3) and another firm (INV-2); the agent and the system at the service.
- **Rollback:** delete the file.

## Progress log
- 2026-10-27: planned and written.
- 2026-10-27: targeted pass: 31 passed, 1 strict xfail. Conclusions answer 201. Defect: ED-117 (a conclusion racing another on the same predecessor answers 500; data intact) held by `test_ac18_a_losing_concurrent_conclusion_answers_409_never_500`, five rounds so the race shows every run.
