---
id: TASK-6600
title: S34 kickoff, the scan and the order
spec: SPEC-000  # sprint record
acceptance_criteria: [AC-1]  # every S34 row is placed: built, finishing, chained, partial or not built
risk_zone: green
status: in-review
branch: s34-kickoff
worktree: /Users/ayushkbhatia/Accrued/abacus-s34
created: 2026-11-10
updated: 2026-11-10
---

## Objective
Place every S34 row against main fd063a888 and order the build.

## Plan
1. [x] Read the S34 section of the sprint plan, the prompt book's Vol 5 S34 block and the 44 backlog rows.
2. [x] Check each dependency by a main commit, a task file and a code probe, not the stale status column.
3. [x] Write `docs/plan/status/S34.md`.

## Progress log
- `2026-11-10` — Scan done; 28 code rows buildable (20 off main, 2 partly, 6 chained), 9 quality lanes, 7 not code.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3200 | S34 order, numbers, dark build on proposed ADRs, what is not built | no |
