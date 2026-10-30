---
id: TASK-2119
title: T-02-T05 Consumer contract tests in the providers' CI
spec: SPEC-502
acceptance_criteria: [AC-6]
risk_zone: amber
status: in-review
epic: T-02
plan_key: T-02-T05
branch: s16-t02-t05
created: 2026-10-29
updated: 2026-10-29
---

## Objective
T-02's consumer suite over C19, C21, C7 and C3, with T-01's `engine_sync.imported` as a strict
xfail citing this task until T-01-T24.

## Progress log
- 2026-10-29: written (S16 block; run at the batch's end review). Note: tests import
  `review.contract` directly (the C3 literals are not re-exported by `review.api`); move to
  `review.api` if a lint objects at the end review.
