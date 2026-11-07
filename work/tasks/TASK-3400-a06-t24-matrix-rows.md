---
id: TASK-3400
title: A-06-T24 Materiality, Findings and the Completion Checklist as reviewables; AUD-17's groups as drawn
spec: SPEC-000  # row (A-06-T24)
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: A-06
plan_key: A-06-T24
branch: s28p-matrix-rows
worktree: /Users/ayushkbhatia/Accrued/abacus-s28
created: 2026-11-08
updated: 2026-11-08
---

## Objective
Part 2 of AUD-17's 26 rows. The design signs Materiality, Findings and the Completion Checklist, and none was a C3 reviewable; its groups also differ from DEC-2238's (Trial Balance in Planning, Form 5500 in Fieldwork & Testing).

## Plan
- `assurance/completion_reviewables.py`: `materiality`, `audit_findings` and `completion_checklist`, one row per audit work item, each hashed from its own records (a change leaves its sign-offs stale), registered with C3 so they reach the matrix and G5.
- Groups: Trial Balance and Materiality in Planning, the sample and the mapping in Fieldwork & Testing, the financial statements in Reporting; Form 5500 Tie-Out in Fieldwork & Testing; a paper with no kind by its audit area.
- Rollback: revert; no migration.

## Progress log
- 2026-11-08: built. `tests/unit/assurance/test_s28_matrix_rows.py` (13); unit assurance, workpapers, review: 511 pass; ruff, pyright clean. Postgres runs with the seed in part 4.

## Decisions made during this task
DEC-2399
