---
id: TASK-7835
title: "P-09-T09: frame 8's Run n picker"
spec: SPEC-000  # code partial (S0-S38 inventory, bucket C)
acceptance_criteria: [AC-1]  # the row's acceptance
risk_zone: green
status: in-review
branch: p09-t09-run-picker
worktree: /Users/ayushkbhatia/Accrued/abacus-lo39-rec
created: 2026-11-14
updated: 2026-11-14
plan_key: P-09-T09
---

## Objective
SHL-13 frame 8's "Run 2 ⌄" was a disabled button waiting on P-09-T13, which has landed (#1564).

## Delivered (#1944)
- `RunPane` takes the dock's run list and `onRun`; `runChoices` lists the open agent's runs oldest
  first, numbered back from the open run's `run_number`; picking another opens it.
- Tests: RunPane suite 21 passed, agents suites 63 passed. The PR ran CI as the frontend-only
  measurement for F-01-T07 (run 43499777873, green).

## Still open in P-09-T09
- Frame 9's trigger line ("Auto-started by trigger: …") needs a trigger label on C6, which exists
  only once K-04-T21 (S61) records engagement triggers.
- Frame 9's step-through card ("Step n of m", "Next: …", "Run all steps") needs a runtime step mode;
  no backlog row owns one (a Temporal workflow change under P-10).
- Frame 10 (thumbs down, reason picker, submit) is built: the feedback route is live.

## Progress log
- 2026-11-14: built, PR #1944.

