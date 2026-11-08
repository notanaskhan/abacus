---
id: TASK-3399
title: A-06-T24 each reviewable's required levels from the firm's review_levels standard
spec: SPEC-000  # row (A-06-T24)
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: A-06
plan_key: A-06-T24
branch: s28p-signoff-levels
worktree: /Users/ayushkbhatia/Accrued/abacus-s28
created: 2026-11-08
updated: 2026-11-08
---

## Objective
Ayush (2026-11-08) chose AUD-17's 26 rows. The design gives each row its own levels (a dash where a level isn't required, a ring where it is and waits; Partner 8 of 13, EQR 0 of 6), but every reviewable required L1 and L2 alone. Part 1 of 4.

## Plan
- K-02's `review_levels` payload gains optional `assignments` (requirement key, required levels); every published version reads as before.
- `methodology.assigned_review_levels(tenant, key, on)`: the in-effect standard's levels for a key.
- `review.reviewable_facts` applies them, so AUD-17's matrix, the G5 gate and the sign-off rules read the same levels; `ReviewableFacts.requirement_key` (default the target type); a workpaper names its kind.
- The workbook export leaves an empty optional list out, so K-02's round trip stays an empty diff.
- Rollback: revert; no migration; with no assignments published nothing changes.

## Progress log
- 2026-11-08: built. `tests/unit/review/test_s28_level_assignments.py` (9); unit review, methodology, workpapers, assurance, sampling: 664 pass (one owner-only module now clears the port, as it does the other registries; K-02's round trip found the empty-list export, fixed). ruff, pyright clean; client regenerated.

## Decisions made during this task
DEC-2398
