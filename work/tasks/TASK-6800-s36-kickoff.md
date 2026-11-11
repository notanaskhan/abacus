---
id: TASK-6800
title: S36 kickoff, the scan and the order
spec: SPEC-000  # sprint record
acceptance_criteria: [AC-1]  # every S36 row is placed: built, chained, partial or not built
risk_zone: green
status: in-review
branch: s36-kickoff
worktree: /Users/ayushkbhatia/Accrued/abacus-s36
created: 2026-11-11
updated: 2026-11-11
---

## Objective
Place every S36 row against main 95da1ef88 and order the build.

## Plan
1. [x] Read the S36 section of the prompt book's Vol 5 and the 39 backlog rows.
2. [x] Check each dependency by its `plan_key` task file, a main commit and a code probe, not the stale status column.
3. [x] Write `docs/plan/status/S36.md`.

## Progress log
- `2026-11-11` — Scan done; 24 code rows buildable (17 off main, 4 chained, 3 partly); 15 not code.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3400 | S36 order, numbers, what is not built | no |
