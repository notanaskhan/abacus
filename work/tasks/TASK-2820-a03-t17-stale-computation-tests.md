---
id: TASK-2820
title: A-03-T17 independent AC tests, part two (the stale computation)
spec: SPEC-580
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: A-03
plan_key: A-03-T17
branch: s23-a03-t17b
worktree: /Users/ayushkbhatia/Accrued/abacus-s23
created: 2026-11-01
updated: 2026-11-01
---

## Objective
- **[AC-1]** "The suite passes on main and fails when any human-only CHECK, the freeze trigger,
  the unmapped guard or the stale computation is removed." Part one (TASK-2815) covered the
  others; this part covers the stale computation A-03-T14 added (DEC-1765).

## Plan (red, tests only)
- Unit, in `tests/unit/ledger/test_a03t17_stale.py`.
- The mapping content hash:
  - It is order-independent.
  - It moves on every change a signer saw: an account added, moved, left unmapped or gone, and the grouping version.
- The follow step asks review's staleness about the view's own hash.
- One `mapping_set.went_stale` goes to the signers when stale, and none when unchanged.
- Rollback: revert.

## Progress log
- `2026-11-01`: written; ruff and pyright clean. The tests run in the end pass (build-first rule).

## Decisions made during this task
None.
