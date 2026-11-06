---
id: TASK-3344
title: N-04-T16 notice timers can fire, and a payment gets its confirmation request
spec: SPEC-000  # row (N-04-T16)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: N-04
plan_key: N-04-T16
branch: s28r-n04-t16b
worktree: /Users/ayushkbhatia/Accrued/abacus-s28
created: 2026-11-06
updated: 2026-11-06
---

## Objective
Fix the alert activities and close DEC-2311's payment partial.

## Plan
- Audit rows on `send_alert` and `send_follow_up`.
- `send_for_signature` adds one confirmation request; `on_review_decision` marks the payment; the Payment band reads it.

## Progress log
- 2026-11-06: built. `tests/unit/notices`, notices contract tests and N-04's core integration suite: 149 passed locally. No integration test runs the review decision through the outbox; it is unit-tested with stubs.

## Decisions made during this task
DEC-2376
