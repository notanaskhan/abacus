---
id: TASK-1292
title: Independent AC suite 1 (ADR-078) for the audit log against the stubs
spec: SPEC-349
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-9, AC-10, AC-11, AC-12, AC-13, AC-14, AC-45, AC-46, AC-47]
risk_zone: red
status: in-review
epic: G-02
plan_key: G-02-T05
branch: s9c-governance
created: 2026-10-26
updated: 2026-10-26
---

## Objective
The ADM-07 acceptance tests, written before the read side (G-02-T08) and the export (G-02-T17),
from SPEC-349 and `docs/contracts/audit-log.md` (G-02-T05).

## Plan
- `backend/tests/integration/test_g02t05_audit_log_ac_suite.py`, headed `# ac-test-author:
  ayushkbhatia`. Over HTTP against `create_app()`, with the sign-in dependency answering as the
  persona (Felix `security_admin`, Grace `firm_admin`, Margaret `quality_partner`, Hannah walled
  from Ashford, a client principal, the agent principal); the flags on in
  `feature_flag_states`; events through `kernel.uow`.
- **How it fails against the stubs while CI stays green.** The lint requires an issue number
  (`#NNN`) in every skip or xfail reason and this branch has none to cite, so the suite uses the
  repo's stub-to-live pattern (`LIVE` in the firm-settings contract tests) instead: `STUBBED`
  lists the five routes still answering 501; a behaviour test on a stubbed route asserts the 501
  and stops. T08 and T17 remove their routes from `STUBBED` and the full assertions run then.
- Tests that need no live route run in full now: AC-3 (the database refuses a human-only action
  written as the agent), AC-8 (no route can change an event; the app role cannot UPDATE or
  DELETE), AC-11 (a reference can never carry a value; no seeded SSN in the trail), AC-45 (the
  matrix).
- The F-04 harness consumer test: `since_seq` tails the log oldest first.
- Rollback: delete the file.

## Progress log
- 2026-10-26: written. 31 pass against the stubs (23 pin the 501, 8 run in full). With `STUBBED`
  emptied the run is 20 failed, 8 passed: every behaviour test fails against the stubs, as the
  row asks. AC-6's SSN probe searches for the digits; seeding an SSN-bearing target for it is
  T10's (the label index), with a client TIN through the clients API.
- Note for the main session: the brief allows `xfail(strict=True)` citing `TASK-NNNN`, but
  `banned_patterns` (SKIP-001) only accepts `#NNN` or an issues URL, so a TASK-only reason fails
  `make check-fast`. Hence `STUBBED` rather than strict xfails.
