---
id: TASK-5132
title: P-10-T11 C6 v2 and C17 consumer contract tests
spec: SPEC-000  # row (P-10-T11)
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: P-10
plan_key: P-10-T11
branch: s29-p10-t11
worktree: /Users/ayushkbhatia/Accrued/abacus-s29
created: 2026-11-06
updated: 2026-11-06
---

## Objective
Fail if a field SHL-13, WB-01, WB-03 or WB-09 reads leaves C6 v2, or a T-04 or I-02 tool shape stops registering.

## Plan
Pytest over the stub models; TypeScript fixtures typed against the generated client.

## Progress log
- 2026-11-06: built. test_c06_v2_consumers.py and c6-v2-consumers.test.ts written; held for the end pass.

## Decisions made during this task
None.
