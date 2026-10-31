---
id: TASK-2812
title: A-05-T06 migration 0610 ebp_core
spec: SPEC-640
acceptance_criteria: [AC-4]
risk_zone: red
status: in-review
epic: A-05
plan_key: A-05-T06
branch: s23-a05-t06 (stacked on s23-a05-t05)
worktree: /Users/ayushkbhatia/Accrued/abacus-s23
created: 2026-11-01
updated: 2026-11-01
---

## Objective
- **[AC-1]** "Upgrade and downgrade pass on the synthetic seed, a walled user reads zero rows, and
  a conflict or check row cannot be updated or deleted."

## Plan (red)
- Migration 0610 (expand-only) on 0580: five tables, forced RLS, column grants, insert-only checks
  and conflicts, no DELETE for the app role. Registry entries (TABLES, INSERT_ONLY, columns).
- Test: `tests/integration/test_a05t06_ebp_core_migration.py` (down/up, RLS, privileges). Also to
  run at the end review: every `test_*migration*` suite and the schema check.
- "Run by the pipeline after 20:00 CT": the deploy pipeline's window, not this PR.
- Rollback: downgrade drops the five tables (nothing reads them yet).

## Progress log
- `2026-11-01` — built; ruff clean. Tests at the S23 end review; re-chain onto main's head right
  before merge if another migration lands first.

## Decisions made during this task
DEC-1861.
