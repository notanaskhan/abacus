---
id: TASK-6013
title: "S29-leftovers leftovers end pass: targeted gates, two fixes, status record"
spec: SPEC-000  # row (S29-leftovers)
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: S29-leftovers
plan_key: S29-leftovers
branch: s29l-end-pass
worktree: /Users/ayushkbhatia/Accrued/abacus-s29
created: 2026-11-07
updated: 2026-11-07
---

## Objective
Every leftovers PR's gates pass on the stack tip, and the status record names what each row still waits on.

## Plan
On the tip: alembic heads (0700 alone), contract snapshots, schema_check, make regenerate (no diff), banned patterns over the whole tree (clean after #1394's fixes), pyright, ruff and format over every changed Python file, every changed unit, contract, golden and workflow test, the six changed integration files, web tsc, eslint, prettier and the touched screens' and fixtures' tests. Fixes: a typed reasons list in test_n04t25_clearance (pyright), test_n04t06_notices_core formatted. docs/plan/status/S29-blocked-and-rituals.md gains the round's table.

## Progress log
- 2026-11-07: built. Backend: 242 passed and 1 strict xfail (changed unit, contract, golden and workflow tests), 39 integration passed, schema_check and contracts clean, banned patterns clean. Web: 217 passed and 1 expected fail across 21 files; tsc, eslint and prettier clean. Not run: the full suites and CI (targeted, as asked).

## Decisions made during this task
None.
