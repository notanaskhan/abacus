---
id: TASK-385
title: Subtype tables and kind providers for returns, closes, notices and advisory projects (F-03-T22)
spec: SPEC-025
acceptance_criteria: [AC-1]
risk_zone: amber
status: done
epic: F-03
plan_key: F-03-T22
branch: f03-t22-work-item-kinds
created: 2026-10-22
updated: 2026-10-22
---

## Objective
"Copperleaf '2026 Close' holds 12 close work items and Thornbury's tax engagement holds four
returns across two entities, all created through engagements.api."

## What changed
- Migration 0089: `tax_returns` (tax), `closes` (closes; one per engagement and `YYYY-MM`
  period), `notices` (notices), `advisory_projects` (engagements); each tied to its work item in
  the same engagement; insert-only for the app; minimal columns (owners extend, expand-only).
- `engagements.create_work_item(ctx, engagement_id, kind, *, name, client_entity_id, due_on,
  details)` behind new action `work_item.create` (partner, manager): the work item and its
  subtype row in one unit of work; a kind's cardinality breach is 409 `work_item_exists`.
- Kind providers: `tax_return`, `close`, `notice` registered by their modules; `assurance` and
  `advisory_project` by engagements. `WorkItemProvider` gains `create`; the kind slot accepts the
  same provider again after a module reload.
- Tests: `tests/integration/test_work_item_kinds.py`.

## Progress log
- 2026-10-22: built. Tests run in the batch's end-of-run CI.
