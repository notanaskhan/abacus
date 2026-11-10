---
id: TASK-6116
title: "A-07-T20 independent I-IMMUTABLE tests for A-07-T13 and T14"
spec: SPEC-000  # row (A-07-T20)
acceptance_criteria: [AC-1]
risk_zone: red
status: done
epic: A-07
plan_key: A-07-T20
branch: s30-a07-t20
worktree: /Users/ayushkbhatia/Accrued/abacus-s30
created: 2026-11-08
updated: 2026-11-08
---

## Objective
ADR-078 tests for the archive guard and the archived-exempt route layer: trigger on every scoped table from the registries, new tables auto-guarded, the GUC only from allowlisted functions, property sequences never mutate a locked row, route-table coverage.

## Plan
- `tests/integration/test_a07t20_immutable_independent.py`: catalog check over every registry-owned table with `work_item_id`/`engagement_id` minus the reviewed exemptions; exemptions name owned tables with reasons; `tenant_table` on a fresh probe table attaches the trigger; ARCHIVE-001 over the whole tree finds nothing outside the allowlist and catches a planted offender; a hypothesis property (15 sequences of updates, deletes, inserts) on a locked work item, every write refused and the row unchanged; T14's generated route-table test exists.

## Progress log
- 2026-11-08: built. Written, not run (tests at the end review). ruff and pyright clean.

## Decisions made during this task
None.
