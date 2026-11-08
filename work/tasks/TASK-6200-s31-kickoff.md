---
id: TASK-6200
title: S31 kickoff, the scan and the order
spec: SPEC-000  # sprint record
acceptance_criteria: [AC-1]  # every S31 row is placed: built, finishing, chained, partial or not built
risk_zone: green
status: in-review
branch: s31-kickoff
worktree: /Users/ayushkbhatia/Accrued/abacus-s31
created: 2026-11-08
updated: 2026-11-08
---

## Objective
Place every S31 row against main a801fff01 and order the build.

## Plan
1. [x] Read the S31 section of the sprint plan, the prompt book's Vol 5 S31 block and the 33 backlog rows.
2. [x] Check each dependency by a main commit and a code probe, not the stale status column.
3. [x] Write `docs/plan/status/S31.md`.

## Progress log
- `2026-11-08` — Scan done; 22 code rows buildable (15 off main, 7 chained), 3 quality lanes, 7 not code.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-2800 | S31 order, numbers and what is not built | no |
