---
id: TASK-8727
title: "T-08-T10: Filing-deadlines derived fields: risk tier, day counts, postponements"
spec: SPEC-710
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
branch: t08-t10-deadlines
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-19
updated: 2026-11-19
plan_key: T-08-T10
---

## Objective
practice/compute/deadlines.py (pure): risk tier (overdue, due in 7, due in 30, later, done) and days left computed on read in the firm's zone, postponements moving the effective date, day and week groupings for HOME-03's month, week and list views.

## Plan (amber)
1. practice/compute/deadlines.py; tests/unit/practice/test_t08t10_deadlines.py.

## Progress log
- `2026-11-19` — Built; tests pass (2). Not built: FilingDeadlineRecomputeWorkflow (outbox events, reference-set publishes, nightly schedule), the read model's rows into filing_deadlines (0962), the month/week/list API with walls and C21 rule text; the Sep 15 '12 items' figure needs the deadlines seed. Gates and tests run once at the S51 end pass (build first, test last).
