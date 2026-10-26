---
id: TASK-1323
title: Independent AC tests (ADR-078) for independence live (P-07-T43)
spec: SPEC-332
acceptance_criteria: [AC-17, AC-18, AC-19, AC-20, AC-21, AC-22, AC-27, AC-28]
risk_zone: amber
status: in-review
epic: P-07
plan_key: P-07-T43
branch: s10b-independence-intake
test_author: ayushkbhatia
test_session: 2026-10-26, branch s10b-independence-intake (written before P-07-T41, following .claude/skills/ac-test-author/SKILL.md)
created: 2026-10-26
updated: 2026-10-26
---

## Objective
"The suite is committed before T41 opens for review and passes unchanged." Self-only
confirmation, decline note, conclusion EP-only with MFA and preconditions (INV-1), breach events
insert-only, rotation derivation, G2 provider and attest-only scope.

## Plan (amber)
- **File (tests only)**: `backend/tests/integration/backfill/test_p07t43_independence_independent.py`.
- **Sources only**: SPEC-332 §5 Stories 5 to 9, P-07 §3.5, §4.2 M7, §4.3, §4.7; the contract
  `docs/contracts/acceptance-independence.md` and its route declarations; the engagements matrix;
  `error-codes.yaml`; `human-only-actions.yaml`; the CLI-08 screen contract.
- **Boundary**: `create_app()` over HTTP (`net`, `seed`) behind `engagements.v2` and
  `engagements.acceptance_v2`; `engagements.api` for the live-human layer; raw SQL for the CHECK
  and insert-only layers; `banned_patterns` for the call-site rule.
- **Markers**: every test needing a live route is `xfail(strict=True)` citing TASK-1325; T41's
  commit removes the markers and changes nothing else.
- **Rollback**: revert the commit.

## Spec gaps followed
- The conclusion's blockers are flat identifier facts, one count per reason code (ADR-139).
- `not_self` cannot arise through the routes (no user id in the body); someone off the team is
  refused at the matrix (403 or 404).
- The SKE designee has no designation route yet: seeded as an `engagement_contacts` row (DEC-63).
- NAS rows are the attest client's engagements outside the attest family (AC-21).
- Rotation's threshold is the platform default of seven years until firm settings hold integers.

## Progress log
- 2026-10-26: written from the sources above before T41. On the stub: 1 passes (the matrix rows),
  the rest are strict xfails citing TASK-1325.
- 2026-10-26 (with T41, TASK-1325): the 19 markers removed; all 21 tests pass. One non-assertion
  edit: the breach-log delete probe lost a `# noqa: S608` (SUPPRESS-001) and became two literal
  statements.
