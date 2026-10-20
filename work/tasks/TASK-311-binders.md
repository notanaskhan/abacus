---
id: TASK-311
title: "F-03-T14 [mig 0070]: binders — request lists on work items with kind, part, status and stamps; request categories"
spec: SPEC-306
acceptance_criteria: [AC-4]
risk_zone: red
status: done
branch: task-311-binders
worktree: spec005
created: 2026-10-20
updated: 2026-10-20
---

## Plan
- Migration **0070** adds to `request_lists`: `work_item_id`, `name`, `kind`, `part`, `status`, the published and marked-done stamps, and `prior_year_source_ref`.
  - Backfill: the assurance work item, the name "Requests", status `published`.
  - The FK to `work_items` replaces the one-list-per-engagement unique with `UNIQUE (tenant_id, work_item_id, kind, part)`.
  - A BEFORE INSERT trigger fills a missing work item (or raises a foreign-key violation).
  - Column UPDATE grant on the status and stamp columns.
  - New `request_categories` table, backfilled from audit areas.
- `requests.request_list_for` reads and creates the first PBC binder (kind `pbc`, part 1), published at once until the BND-01 publish flow exists.
- Rollback: downgrade 0070.

## Definition of done
- [x] Local backfill: 36 lists linked and published, 86 categories.
- [x] up/down/up passes (schema_check).
- [x] Integration: second binder (part 2) succeeds; a duplicate part is refused; the missing-engagement FK test passes.
- [x] Requests unit, evidence and engagements integration (288) pass.
- [x] check-fast passes.
