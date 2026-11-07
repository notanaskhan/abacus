---
id: TASK-3392
title: A-06-T28 Granite Peak's declined entry, and pre-tax income as a benchmark
spec: SPEC-000  # row (A-06-T28)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: A-06
plan_key: A-06-T28
branch: s28q-a06-granite
worktree: /Users/ayushkbhatia/Accrued/abacus-s28
created: 2026-11-07
updated: 2026-11-07
---

## Objective
Load Granite Peak's J22 step 8. It needed materiality, and proposing it failed for a product reason: no commercial FS audit could propose materiality at all.

## Plan
`read_benchmark` derives pre-tax income from accounts mapped to revenue and expense groupings. Seed: Hannah on the team, 5% decided Sep 14, the SURL finding, its entry, sent to Luis, declined Oct 5, passed by Margaret. Test the SUM's thresholds.

## Progress log
- 2026-11-07: built. `test_a06t28_completion_load.py`: 12 passed, including Granite's 155,000 / 116,250 / 7,750 in the commercial column set.

## Decisions made during this task
DEC-2391
