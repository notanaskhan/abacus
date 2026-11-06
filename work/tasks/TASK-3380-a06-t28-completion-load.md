---
id: TASK-3380
title: A-06-T28 completion scenario loaded through the services
spec: SPEC-000  # row (A-06-T28)
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: A-06
plan_key: A-06-T28
branch: s28p-a06-t28
worktree: /Users/ayushkbhatia/Accrued/abacus-s28
created: 2026-11-06
updated: 2026-11-06
---

## Objective
The rest of the row after TASK-3339's checklist: Northwind's findings, entries, SUM, notes, sign-offs and statements, through the services as the people the design names.

## Plan
- Services the load needs and that didn't exist: projected misstatements from sampling's counts, stated effects and nature, below-CT by code, context-only prior year, a paper's kind, record-mode management approval. No migration: 0644 and 0660 already hold the columns.
- `completion_slice.py` and the loader's `_completion_*` handlers; a second grouping set for the plan's statement of net assets.
- Rollback: revert; the slice is opt-in.

## Progress log
- 2026-11-06: built. `tests/integration/test_a06t28_completion_load.py` (7) at snapshot 2026-10-21T14:10. See DEC-2373 for what stays partial. Bugs it found are in the decision.

## Decisions made during this task
DEC-2373
