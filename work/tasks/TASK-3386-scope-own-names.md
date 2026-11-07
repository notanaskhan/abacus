---
id: TASK-3386
title: Outbound scope reads a number in an own name as an amount
spec: SPEC-000  # row (none)
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
branch: s28q-ci-r01t24
worktree: /Users/ayushkbhatia/Accrued/abacus-s28
created: 2026-11-07
updated: 2026-11-07
---

## Objective
The one CI failure read so far on run 42281021804.

## Plan
- `communications/scope.py`; a test in `test_r01t24_scheduled_send.py`. Rollback: revert.

## Progress log
- 2026-11-07: fixed. 135 passed across the scope and reminder tests. See DEC-2385.

## Decisions made during this task
DEC-2385
