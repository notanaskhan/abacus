---
id: TASK-3258
title: A-06-T23 sign-off matrix and EP-involvement read models (AUD-17)
spec: SPEC-000  # row (SPEC-642 AC-23)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: A-06
plan_key: A-06-T23
branch: s27-a06-t23
worktree: /Users/ayushkbhatia/Accrued/abacus-s27
created: 2026-11-04
updated: 2026-11-04
---

## Objective
"The Northwind matrix returns 26 = 6 + 3 + 7 + 6 + 4 rows with footer Prepared 25, Reviewed 24,
Partner 8 of 13, EQR 0 of 6 and one Changed after sign-off."

## Plan (amber)
- `assurance/review_matrix.py`: rows from every registered reviewable × L1–L5 (signed, stale,
  pending, not required; initials, version, hash prefix), sections by paper kind
  (`workpapers.api.matrix_sections`, new) with engagement-level reviewables in Completion, the
  footer by code; the EP-involvement timeline from the EP's decided cards and L4 sign-offs.
- `review.api.decided_cards` (new read: kind, question key, option, decider, time; no rationale).
- Routes on the A-06 completion router: `GET …/sign-off-matrix?section=` and
  `GET …/ep-involvement` (`sign_off.read`, behind `assurance.completion`).
- Schemas prefixed `SignOffMatrix…` (review's `MatrixRowOut` exists); client regenerated.
- Tests: `tests/unit/assurance/test_a06t23_review_matrix.py` (footer and cell rules); the seeded
  Northwind figures belong to A-06-T21's suite and the AUD-17 journey.

## Progress log
- 2026-11-04: built.

## Decisions made during this task
DEC-2238.
