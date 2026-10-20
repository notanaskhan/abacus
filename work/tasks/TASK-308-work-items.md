---
id: TASK-308
title: "F-03-T05: work items — work_items, assurance_work_items, work_item_assignments, engagement_entities; one assurance item and one primary entity per engagement"
spec: SPEC-306
acceptance_criteria: [AC-1]
risk_zone: red
status: done
branch: task-308-s1-migrations
worktree: spec005
created: 2026-10-20
updated: 2026-10-20
---

## Plan
- Migration **0068**: the plan's "0056_work_items", renumbered because main is at 0067.
  - New tables: `work_items` (partial unique index: one assurance item per engagement), `assurance_work_items`, `work_item_assignments` (insert-only) and `engagement_entities` (insert-only, one primary).
  - A backfill as the owner, lifting forced RLS for the statement as 0036 does.
  - An `engagement_work_item_defaults` AFTER INSERT trigger, so every insert path (service, tooling, tests) keeps the invariant. `seed_dev` needs no change.
- `engagements/work_items.py` and `GET /v1/engagements/{id}/work-items` (`work_item.read_metadata`).
- schema_check registrations.
- Rollback: downgrade 0068.

## Definition of done
- [x] Local backfill gives 52 engagements, 52 assurance items and 52 primary links.
- [x] up/down/up passes (schema_check).
- [x] `tests/integration/test_work_items.py` (3) passes.
- [x] check-fast passes.
