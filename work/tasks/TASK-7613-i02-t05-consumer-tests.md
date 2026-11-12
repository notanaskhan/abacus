---
id: TASK-7613
title: I-02-T05 consumer contract tests for the Today family
plan_key: I-02-T05
spec: SPEC-654
acceptance_criteria: [AC-1]  # green against the stubs; fail on a removed field or a model-text field feeding a count
risk_zone: amber
status: in-review
branch: i02-t05-consumer-tests
worktree: /Users/ayushkbhatia/Accrued/abacus-s40
created: 2026-11-12
updated: 2026-11-12
---

## Objective
The Today family's consumer tests in the providers' CI: a pytest half against the practice stub
and the questions route, and a TypeScript half validating SHL-23 1–7 and HOME-05 a–f fixtures.

## Plan
- `backend/tests/contracts/today/test_today_consumer.py`: six routes, one action each, 501 by
  `UNBUILT`; per-artboard field lists; no `blocks` field on a count model and counts typed integer
  (I-COUNT); classification (question text Restricted); no hidden or wall field; refused principals.
- `apps/web/src/fixtures/contracts/today.contract.test.ts`: every fixture validated; Daniel 11,
  Margaret 4; Due tomorrow 9 and Ready for sign-off 4; Late always present; reserved items never
  prefilled.
- Rollback: delete the two files.

## Partial
- The `agents.api` briefing read shapes (`EngagementBriefing` blocks, unavailable reasons, build
  status) arrive with I-02-T07/T08/T13; their consumer assertions join this suite then.

## Progress log
- `2026-11-12` — Both halves written. Run at the S40 end pass.
