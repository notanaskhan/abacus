---
id: TASK-5134
title: A-05-T47 Independent goldens for EBP-05, EBP-06, EBP-08, EBP-09
spec: SPEC-000  # row (A-05-T47)
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: A-05
plan_key: A-05-T47
branch: s29-a05-t47
worktree: /Users/ayushkbhatia/Accrued/abacus-s29
created: 2026-11-06
updated: 2026-11-06
---

## Objective
Every acceptance figure in the four handoff specs is a golden with exact Decimal equality.

## Plan
tests/golden/ebp/test_a05t47_ebp_goldens.py against the engines: loans, withholding, vesting, expenses, limits, participant ties, certification hold.

## Progress log
- 2026-11-06: built. 27 goldens pass.

## Decisions made during this task
None.
