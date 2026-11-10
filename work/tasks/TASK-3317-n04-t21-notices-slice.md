---
id: TASK-3317
title: N-04-T21 Brightwater Hale notices scenario N1 to N9
spec: SPEC-000  # row (N-04-T21)
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: N-04
plan_key: N-04-T21
branch: s28-n04-t21
worktree: /Users/ayushkbhatia/Accrued/abacus-s28
created: 2026-11-05
updated: 2026-11-05
---

## Objective
"make seed-demo produces every NOT artboard's data through service APIs, the fixture and seed exports are equal, and no template text appears in any migration or constant."

## Plan
- `notices_content.py`: N1 to N9 with the seed counts; `files/notice_templates.yaml`.
- Loader handler through intake and service moves.
- Rollback: drop the slice.

## Progress log
- 2026-11-05: built. Tests at the S28 end review.

## Decisions made during this task
DEC-2316
