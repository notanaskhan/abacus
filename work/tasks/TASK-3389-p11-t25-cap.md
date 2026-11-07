---
id: TASK-3389
title: P-11-T25 the forms call and the daily cap, as built
spec: SPEC-000  # row (P-11-T25)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: P-11
plan_key: P-11-T25
branch: s28q-p11-cap
worktree: /Users/ayushkbhatia/Accrued/abacus-s28
created: 2026-11-07
updated: 2026-11-07
---

## Objective
DEC-2383 said forms calls aren't in the daily page cap's count. They are: `over_daily_cap` sums `page_units` over every `ocr_runs` row. Correct the record and pin the behaviour.

## Plan
Correct the clause, record the decision, add a Postgres test. No product change.

## Progress log
- 2026-11-07: built. `-k cap` on `test_p11t25_ocr_run.py`: 2 passed.

## Decisions made during this task
DEC-2388
