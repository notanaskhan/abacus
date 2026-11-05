---
id: TASK-3302
title: A-07-T08 migration 0668 letters, report and release (A-07 M2)
spec: SPEC-000  # row (A-07-T08)
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: A-07
plan_key: A-07-T08
branch: s28-a07-t08
worktree: /Users/ayushkbhatia/Accrued/abacus-s28
created: 2026-11-05
updated: 2026-11-05
---

## Objective
"A second original release for the same work item and any UPDATE of a version or release row are refused by the database."

## Plan
- Migration 0668 on 0667 (expand-only), A-07 §4.2 M2, eleven tenant tables; insert-only triggers via 0664's `a07_rows_immutable`.
- Partial unique index `report_releases_one_original`.
- Registry `A07_LETTER_TABLES`; schema_check's immutable map; tenant list; human-only actions list.
- Tests: A-07-T10 (`tests/integration/test_a07t10_letters_archive_migrations.py`).
- Rollback: downgrade drops the tables and restores 0664's human-only list.

## Progress log
- 2026-11-05: built. Tests at the S28 end review.

## Decisions made during this task
DEC-2302
