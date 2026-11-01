---
id: TASK-2640
title: Raise the route-chunk bundle budget to 135 KB (founder decision)
spec: SPEC-000  # chapter 04 §1 rule 13 and §11; scripts/bundle-budget.mjs
acceptance_criteria: [AC-1]  # `pnpm build:portal` passes its budget step
risk_zone: green
status: in-review
epic: F-05
plan_key: F-05-T17
branch: s21-route-budget
worktree: /Users/ayushkbhatia/Accrued/abacus-s21
created: 2026-11-01
updated: 2026-11-01
---

## Objective
The build's `spa` job: `build:portal` failed its budget step with five route chunks over 120 KB.

## Scope
`BUDGETS.route` 135 KB in `apps/web/scripts/bundle-budget.mjs`; its two test files; chapter 04's
budget lines (DEC-1682). Local `vite build --mode portal`: portal check 24 files clean, 12 budgets
met. Rollback: revert.

## Progress log
- 2026-11-01: built; budget tests 21 passed.
