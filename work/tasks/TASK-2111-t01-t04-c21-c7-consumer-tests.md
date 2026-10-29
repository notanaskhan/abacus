---
id: TASK-2111
title: T-01-T04 C21 and C7 consumer contract tests written by T-01
spec: SPEC-501
acceptance_criteria: [AC-10]
risk_zone: amber
status: in-review
epic: T-01
plan_key: T-01-T04
branch: s16-t01-t04
created: 2026-10-29
updated: 2026-10-29
---

## Objective
T-01's consumer suites for C21 (8879 form set, Pub 1345 tolerances, version ids) and C7 (envelope
sources, signer-level counts), with N-02's two owed pieces as strict xfails citing this task.

## Plan
- `backend/tests/contracts/c21_t01/test_c21_t01_consumer.py`, `backend/tests/contracts/c7_t01/test_c7_t01_consumer.py`.
- Open with N-02: the `superseded_by_change` marker and the retention-extension call (xfail strict).

## Progress log
- 2026-10-29: written (S16 block; run at the batch's end review).
