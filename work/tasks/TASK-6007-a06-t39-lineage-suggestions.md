---
id: TASK-6007
title: "A-06-T39 the partial's last checks: lineage through C4, agent answers stay suggestions"
spec: SPEC-000  # row (A-06-T39)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: A-06
plan_key: A-06-T39
branch: s29l-a06-t39
worktree: /Users/ayushkbhatia/Accrued/abacus-s29
created: 2026-11-07
updated: 2026-11-07
---

## Objective
Tests written in ayushkbhatia's session pass on main without edits to N's code or tests and fail if an override without a reason is stored or if v1 reports anything but 62 of 63 with the RJE-1 cause.

## Plan
Three tests added to tests/unit/reporting/test_a06t39_statements_independent.py, no change to statements code: `lineage` returns only the citations C4 verifies (one of two dropped) with each source kind; `disclosure_view` doesn't count an agent's suggested answer as answered (1 of 3); `adopt_item` refuses anything but a suggestion (NoSuggestion) and a stale version (StaleAnswer). Rollback: revert.

## Progress log
- 2026-11-07: built. tests/unit/reporting/test_a06t39_statements_independent.py passes (12), pyright clean.

## Decisions made during this task
None.
