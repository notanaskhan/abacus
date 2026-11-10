---
id: TASK-6604
title: "P-05-T08: AC suite for the audit_trail engagement routes plus P-05's consumer contract tests for C3, C13 and C16"
spec: SPEC-650
acceptance_criteria: [AC-7, AC-8, AC-15, AC-30, AC-32, AC-34, AC-36, AC-38, AC-39]
risk_zone: red
status: in-review
branch: s34-p05-t08
worktree: /Users/ayushkbhatia/Accrued/abacus-s34
created: 2026-11-10
updated: 2026-11-10
plan_key: P-05-T08
---

## Objective
Suites assert 12+11+0=23 on the seed, export needs export.create with fresh MFA, staff gain no
ADM-07 access, and comments and to-dos never block sign-off or enter the human-gate projection.

## Plan (red)
1. `backend/tests/contracts/collaboration_p05/test_p05t08_consumers.py`: C16 (`mention.created`
   a second source of `mention`, `todo_assigned` registered, no body in a sentence, AC-8
   fan-out re-check), C13 (no collaboration gate source), C3 (no collaboration reviewable), the
   AUD-29 matrix readers, export's fresh MFA.
2. `backend/tests/integration/backfill/test_p05t08_activity_ac.py`: AUD-29 over HTTP on a 12 + 11
   seed; strict xfail citing this task until P-05-T11 answers (S35); the flag-off 404 runs now.
3. No production code. Rollback: delete the files.

## Progress log
- `2026-11-10` — Written from SPEC-650 and the stubs (solo independence, DEC-3201). Not run (end
  pass). The four AUD-29 route tests are strict xfails citing TASK-6604: P-05-T11 removes the mark
  when it builds the routes (S35). The sign-off half of AC-15 is structural here (no reviewable or
  gate source is a collaboration object); the L2 sign-off walk joins with P-05-T09's conversion.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| — | Covered by DEC-3201 | no |
