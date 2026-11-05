---
id: TASK-3308
title: A-05-T43 EBP-09 service: expenses, budget account, limits by plan year and compliance
spec: SPEC-000  # row (A-05-T43)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: A-05
plan_key: A-05-T43
branch: s28-a05-t43
worktree: /Users/ayushkbhatia/Accrued/abacus-s28
created: 2026-11-05
updated: 2026-11-05
---

## Objective
"Expenses foot to 38,400 = 6,000 + 32,400, the budget account rolls to 750, and 2025 limits apply, never prior-year limits."

## Plan
- `assurance/compute/ebp/expenses.py`; PROTECTED `reference/irs_plan_limits.yaml` (requires CPA review).
- `assurance/ebp_expenses.py`; routes plan-expenses, erisa-budget-account, compliance-tests, plan-qualification, request-support.
- Rollback: restore the stub; no schema.

## Progress log
- 2026-11-05: built. Tests at the S28 end review.

## Decisions made during this task
DEC-2307
