---
id: TASK-1257
title: Independent AC tests (ADR-078) for acceptance and conflicts (P-07-T38)
spec: SPEC-332
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-9, AC-10, AC-11, AC-23, AC-24, AC-25, AC-26]
risk_zone: red
status: in-review
epic: P-07
plan_key: P-07-T38
branch: s9a-engagement-lifecycle
test_author: ayushkbhatia
test_session: 2026-10-26, branch s9a-engagement-lifecycle (written before P-07-T35 and T36, following .claude/skills/ac-test-author/SKILL.md)
created: 2026-10-26
updated: 2026-10-26
---

## Objective
"The suite is committed before T35 and T36 open for review and passes unchanged." EP-only
decision with fresh MFA at the matrix, live-human, database and banned-pattern layers (INV-1),
rationale rules, immutability, risk-partner review, G1 before the letter, conflict redaction for
walled users (INV-3), clearance audit.

## Plan (red zone)
- **Files (tests only)**: `backend/tests/integration/backfill/test_p07t38_acceptance_independent.py`
  (SPEC-332 AC-1 to AC-11, P-07 §3.4 Story 4.1) and
  `backend/tests/integration/backfill/test_p07t38_conflicts_independent.py` (AC-23 to AC-26,
  P-07 §3.3 Story 3.1's conflict bullets).
- **Sources only**: SPEC-332, P-07 §3.3, §3.4, §4.2 M5 and M6, §4.3, §4.7;
  `docs/contracts/acceptance-independence.md`; the engagements and organisations matrices;
  `error-codes.yaml`; `human-only-actions.yaml`; CLI-06 and CLI-07 screen contracts; the route
  declarations and the plan in TASK-1258 and TASK-1259 for table names (the questionnaire
  template is database content with no import route yet, so the suite seeds it as SQL).
- **Boundary**: `create_app()` over HTTP (`net`, `seed`), `engagements.api` / the database for the
  live-human and CHECK layers, `abacus_tools.quality.banned_patterns` for the call-site rule.
- **Markers**: each test that fails on the stubs carries `xfail(strict=True)` citing TASK-1258 or
  TASK-1259 and the PR main was at (#409); the implementing commit removes the marker and changes
  nothing else.
- **Rollback**: revert the commit.

## Progress log
- 2026-10-26: planned.
- 2026-10-26: written from SPEC-332, P-07 §3.3 and §3.4, the contract, matrices and the plans in
  TASK-1258 and TASK-1259 before either was built. On the stubs: 32 xfailed (each needs a live
  route), 3 passed (the matrix rows for `acceptance.decide` and the conflict actions, and the
  50-name bound, which the request model already holds).
