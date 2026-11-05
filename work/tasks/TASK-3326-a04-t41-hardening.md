---
id: TASK-3326
title: "A-04-T41 hardening: section draft replay, I-AGENT-NEVER, floor at the end pass"
spec: SPEC-000  # row (A-04-T41)
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: A-04
plan_key: A-04-T41
branch: s28-a04-t41
worktree: /Users/ayushkbhatia/Accrued/abacus-s28
created: 2026-11-05
updated: 2026-11-05
---

## Objective
"The mutation score on assurance/compute is at least 75%, the three p95 budgets hold on staging, and both replay histories pass in CI."

## Plan
- `record_section_draft` and its replay test (history at the end pass).
- `tests/contracts/s28/test_a04t41_hardening.py`.
- Mutation floor measured in the end pass; p95 budgets need staging.

## Progress log
- 2026-11-05: built. Tests at the S28 end review.

## Decisions made during this task
DEC-2323
