---
id: TASK-6009
title: "N-04-T23 time-skipping tests for the response alerts and the 60-day follow-up"
spec: SPEC-000  # row (N-04-T23)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: N-04
plan_key: N-04-T23
branch: s29l-n04-t23
worktree: /Users/ayushkbhatia/Accrued/abacus-s29
created: 2026-11-07
updated: 2026-11-07
---

## Objective
Every response-chain rule is proven by tests written outside the implementing session and all pass on main.

## Plan
tests/workflows/test_n04t23_response_timers.py: NoticeResponseWorkflow on temporalio.testing.WorkflowEnvironment.start_time_skipping() with stub activities that record their calls. CP2000 alerts at 7 then 2 days left across continue-as-new; CP3219A at 30, 14, 7, 2; `sent` cancels the alerts still due; the follow-up fires on its day (respond-by + 60) and the run ends on the agency's reply; `respond_by_changed` moves the alerts. No production change. Rollback: revert.

## Progress log
- 2026-11-07: built. tests/workflows/test_n04t23_response_timers.py passes (5) in 2 s of wall time.

## Decisions made during this task
DEC-2608
