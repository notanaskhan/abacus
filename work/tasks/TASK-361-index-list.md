---
id: TASK-361
title: T1 IndexList with FilterBar and StatusTileRow on the list-envelope view model; states T1a to T1e (F-05-T28)
spec: SPEC-048
acceptance_criteria: [AC-8]
risk_zone: green
status: done
epic: F-05
plan_key: F-05-T28
branch: f05-t28-index-list
created: 2026-10-22
updated: 2026-10-22
---

## Objective
"T1a to T1e render from typed view models, tiles never count themselves out, and T1c hides tiles
and the count."

## Scope
**In**
- `packages/ui/src/templates/index-list.tsx`: `IndexList<Row>` over `ListEnvelope<Row>` (P-36),
  with the filter bar (split chips, Clear), the status tile row (tiles filter; counts from the
  server), and the pane (search, count, centred title, New, hairline table, 38/44 rows, selection).
  Its body runs through `ViewStateBody` (loading, empty, filtered-empty, error, restricted, flag-off).
- `ViewStateBody` takes `skeletonCount` (T1e draws 8 rows).
- T1 specimen with the five artboards from the T1 handoff.

**Out**
- Moving the screens that use the TASK-101 `DataTable` to `IndexList`: with each screen.
- Infinite scroll on `next_cursor`: with the first screen over 50 rows.

## Definition of done
- [x] 9 tests in `templates/index-list.test.tsx`
- [x] F-05-T24 harness over the T1 specimen
- [x] `make check-fast`
