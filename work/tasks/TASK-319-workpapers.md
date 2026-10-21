---
id: TASK-319
title: "A-04 first slice: working papers (grid, formulas, citations) and P-04 sign-offs"
spec: SPEC-308
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6]
risk_zone: amber
status: done
branch: task-319-workpapers
worktree: spec005
created: 2026-10-21
updated: 2026-10-21
---

## Plan
- **Migration 0072:**
  - renames `workpaper_versions` and `workpaper_signatures` to `procedure_workpaper_*` (fieldwork models and registry follow);
  - creates `workpapers`, `workpaper_sections`, `workpaper_cells`, `workpaper_cell_citations`, `workpaper_versions` and `sign_offs`, all insert-only with forced RLS;
  - rollback is the downgrade (drops the tables and renames back).
- **The `review` module:** `sign_offs` and `record_sign_off` (run inside the owner's unit of work), plus `states_of` and `sign_off_states`. Matrix file: `review.yaml`.
- **The `workpapers` module:** the formula engine (`formulas.py`), repository, service and routes. Matrix file: `workpapers.yaml`. The engagements api gains `assurance_item_id`.
- **Web:** `Workpapers.tsx` (the index), `Workpaper.tsx` (the grid and rail), the route, and the tab.

## Notes
- Two pinned lists in `test_schema_check_db.py` were stale from F-03 and F-05 (request_items, request_lists, work_items, assurance_work_items, engagements insert columns). They are brought up to date here.
- `test_preregistration.py` now names its landed modules (review, workpapers).

## Definition of done
- [x] `tests/unit/workpapers` (14) and the pinned gate tests pass, and the schema_check db tests pass.
- [x] A local DB smoke test of the repository SQL (newest cell, version, sign-off) passes.
- [x] `spec308workpapers.test.tsx` (5) passes.
- [x] check-fast passes.
