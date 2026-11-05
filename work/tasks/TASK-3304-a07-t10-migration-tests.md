---
id: TASK-3304
title: A-07-T10 AC tests for migrations 0664, 0668 and 0669
spec: SPEC-000  # row (A-07-T10)
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: A-07
plan_key: A-07-T10
branch: s28-a07-t10
worktree: /Users/ayushkbhatia/Accrued/abacus-s28
created: 2026-11-05
updated: 2026-11-05
---

## Objective
"Tests pass and fail when any insert-only or human-only trigger is removed."

## Plan
- `tests/integration/test_a07t10_letters_archive_migrations.py`: names each trigger and exercises it; human-only CHECKs against the GUCs; one original release; 60-day date; retention floor; sealed columns.
- Carries the human-only actions registry for 0668 (generated `_human_only_actions.py`).

## Progress log
- 2026-11-05: built. Tests at the S28 end review.

## Decisions made during this task
None.
