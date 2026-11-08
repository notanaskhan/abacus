---
id: TASK-5304
title: A-05-T17 Version 1 ribbon, SPD conflict, Raise and Sign off wired
spec: SPEC-000  # row
acceptance_criteria: [AC-1]  # b2's ribbon, c's SPD switch and the live paper, hashes and sign-offs
risk_zone: amber
status: done
epic: A-05
plan_key: A-05-T17
branch: s25-a05-t17-ribbon
worktree: /Users/ayushkbhatia/Accrued/abacus-s25
created: 2026-11-06
updated: 2026-11-06
---

## Objective
EBP-02's open clauses that do not wait on SHL-08, and the live read the screen needs.

## Plan (amber)
- Service and contract: `version_diff`, `conflict_source` (both additive); `review_of` returns the
  paper, its sign-offs and the value hashes.
- Screen: ribbon, Read-only pill, band, dock switch, Raise and Sign off overlays. Route: `?version=`.
- Tests: `apps/web/src/screens/EBP-02/EBP-02.test.tsx`, `tests/unit/assurance/test_a05t16_provisions.py`.
- Rollback: revert. No migration.

## Progress log
- 2026-11-06: built. Still open: the viewer's line and page (DV-EBP-02-3), SHL-07 on the reference,
  the rail's child row (DV-EBP-02-5); a live conflict stays null until A-05-T16 (DV-EBP-02-6).

## Decisions made during this task
DEC-2487.
