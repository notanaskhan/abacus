---
id: TASK-6700
title: S35 kickoff, the scan and the order
spec: SPEC-000  # sprint record
acceptance_criteria: [AC-1]  # every S35 row is placed: built, chained, partial or not built
risk_zone: green
status: in-review
branch: s35-kickoff
worktree: /Users/ayushkbhatia/Accrued/abacus-s35
created: 2026-11-10
updated: 2026-11-10
---

## Objective
Place every S35 row against main fa1500814 and order the build.

## Plan
1. [x] Read the S35 section of the prompt book's Vol 5 and the 48 backlog rows.
2. [x] Check each dependency by its `plan_key` task file, a main commit and a code probe, not the stale status column.
3. [x] Write `docs/plan/status/S35.md`.

## Progress log
- `2026-11-10` — Scan done; 36 code rows buildable (19 off main, 15 chained, 2 partly) plus A-07-T41 carried in; 12 not code.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3300 | S35 order, numbers, what is not built | no |
