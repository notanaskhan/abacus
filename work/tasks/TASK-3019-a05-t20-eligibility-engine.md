---
id: TASK-3019
title: A-05-T20 eligibility engine
spec: SPEC-640
acceptance_criteria: [AC-18]
risk_zone: amber
status: in-review
epic: A-05
plan_key: A-05-T20
branch: s25-a05-t20 (stacked on s25-p04-t59)
worktree: /Users/ayushkbhatia/Accrued/abacus-s25
created: 2026-11-02
updated: 2026-11-02
---

## Objective
"Kwame's missed amounts are 2,472 and 1,442, Yuki's are 3,168 and 1,848, and the population query
returns exactly 4 participants."

## Built
`assurance/compute/ebp/eligibility.py`; `tests/unit/assurance/test_a05t20_eligibility.py`.

## Progress log
- 2026-11-02: built; goldens checked (2,472.00 / 1,442.00; 3,168.00 / 1,848.00). The engine reads
  defaults until A-05-T16 publishes the verified provisions (DEC-2066).

## Decisions made during this task
DEC-2066.
