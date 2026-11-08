---
id: TASK-3398
title: A-06-T24 the matrix footer's Reviewed counts as the handoff does
spec: SPEC-000  # row (A-06-T24)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: A-06
plan_key: A-06-T24
branch: s28p-a06-t24-matrix
worktree: /Users/ayushkbhatia/Accrued/abacus-s28
created: 2026-11-08
updated: 2026-11-08
---

## Objective
Ayush (2026-11-08) chose the handoff's Reviewed over DEC-2238's. AUD-17's footer reads 'Reviewed 24' of 26: every row but the unprepared Completion Checklist and the stale Contributions & Remittance review.

## Plan
- `assurance/review_matrix.py`: `reviewed(row)` is prepared (L1 signed, current) and every required L2 and L3 signed on current content; `footer_of` counts those rows.
- Unit tests from the drawn rows.
- Rollback: revert.

## Progress log
- 2026-11-08: built. `tests/unit/assurance/test_a06t23_review_matrix.py` (new test from AUD-17's drawn rows; the existing footer test's Reviewed moves from 2 to 1 under the decided rule); assurance matrix tests 28 pass; ruff, pyright clean.

## Decisions made during this task
DEC-2397
