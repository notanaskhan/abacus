---
id: TASK-3342
title: T-03-T11: TAX-13 leaves planned with its designed links wired
spec: SPEC-000  # row (T-03-T11)
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: T-03
plan_key: T-03-T11
branch: s28r-tax13-links
worktree: /Users/ayushkbhatia/Accrued/abacus-s28
created: 2026-11-06
updated: 2026-11-06
---

## Objective
Lift TAX-13 off `planned` (DEC-2325): wire TAX-01, TAX-02 and CLI-07 from the screen.

## Plan
- `ExtensionRowOut` gains `client_id` and `engagement_id`; links through `to.*`; manifest `fixture`.

## Progress log
- 2026-11-06: built. `TAX-13.test.tsx`, `link-contract.test.ts`, `test_t03t07_schedules.py` and T-03 contract tests pass locally; `tsc` clean.

## Decisions made during this task
DEC-2331
