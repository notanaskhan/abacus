---
id: TASK-5310
title: A-05-T17 SHL-07 citation popover on EBP-02's references
spec: SPEC-640
acceptance_criteria: [AC-1]  # the row's SHL-07 on AA references
risk_zone: green
status: done
epic: A-05
plan_key: A-05-T17
branch: s25d-a05-t17
worktree: /Users/ayushkbhatia/Accrued/abacus-s25d
created: 2026-11-08
updated: 2026-11-08
---

## Objective
The row's "SHL-07 on AA references": the reference opens the value's citation card.

## Plan
`SourceMatchOut` `title`, `loc`, `quote` (additive; client regenerated); EBP-02's reference button and
`CitationPopoverHost`; fixture card for Plan year. Rollback: revert.

## Tests
`EBP-02.test.tsx` ("SHL-07: the reference opens the citation's card"); `test_a05t16_plan_reads.py`.

## Progress log
- 2026-11-08: built. The b2 test's tick query now names the tick buttons, since the row holds a
  second button (the reference); it still asserts every tick is disabled.

## Decisions made during this task
DEC-2491.
