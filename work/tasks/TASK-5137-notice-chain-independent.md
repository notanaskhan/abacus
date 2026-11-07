---
id: TASK-5137
title: N-04-T23 Independent tests of the response chain
spec: SPEC-000  # row (N-04-T23)
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: N-04
plan_key: N-04-T23
branch: s29-n04-t23
worktree: /Users/ayushkbhatia/Accrued/abacus-s29
created: 2026-11-06
updated: 2026-11-06
---

## Objective
Prove each response-chain rule outside the implementing session.

## Plan
tests/unit/notices/test_n04t23_independent.py with hypothesis properties; replays already in tests/workflows.

## Progress log
- 2026-11-06: built. Passes. Not covered here: time-skipping for alerts and the 60-day follow-up, since the repo has no time-skipping harness; the days are tested as pure functions and the workflow by replay.

## Decisions made during this task
None.
