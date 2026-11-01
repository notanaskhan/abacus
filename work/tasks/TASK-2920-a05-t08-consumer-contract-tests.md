---
id: TASK-2920
title: A-05-T08 consumer contract tests on behalf of A-05 (C3, C8, C9)
spec: SPEC-640
acceptance_criteria: [AC-6]
risk_zone: amber
status: in-review
epic: A-05
plan_key: A-05-T08
branch: s24-a05-t08 (stacked on s24-a06-t05)
worktree: /Users/ayushkbhatia/Accrued/abacus-s24
created: 2026-11-01
updated: 2026-11-01
---

## Objective

A-05's consumer tests on the contracts its screens read, run in the providers' CI.

## Plan

- `backend/tests/contracts/a05_consumers/test_a05t08_consumers.py`: C8's AJE-1 pill states (in the vocabulary) and the adjusted TB's four layers; C9's layer view per layer and `layer_unavailable` for Final until a source registers; C3's decide and sign-off actions.
- C8 became available with A-06-T05, so this row stacks on it.

## Progress log

- 2026-11-01: written in abacus-s24. Not run.
