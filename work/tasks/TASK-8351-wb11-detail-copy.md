---
id: TASK-8351
title: "W-01-T16: WB-11's detail copy from the catalogue: write and never rows, who can use it, Configure mappings"
spec: SPEC-659
acceptance_criteria: [AC-20, AC-21, AC-22, AC-23]
risk_zone: red
status: in-review
branch: wb11-detail-copy
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-16
updated: 2026-11-16
plan_key: W-01-T16
---

## Objective
Spec section: SPEC-659 AC-20 to AC-23; WB-11 a. WB-11's detail copy from the catalogue: write and never rows, who can use it, Configure mappings.

## Plan (red)
1. 0933: `integration_catalog.detail_copy` (jsonb object, catalogue content); `integration_catalog_workbench()` answers it and `integration_catalog_import` compares and writes it.
2. `catalog_import.DetailCopyIn` (writes with label and gate label, each one of the row's declared writes; never lines; who can use it and its note); COMPARED gains the column.
3. The drawer: write rows on only when the write-capability registry enables them; a firm app's never rows from the catalogue (a personal app's from its consent); who can use it (`who_can_use_note`, additive); Configure mappings… to ADM-08 for a viewer holding the firm actions.

## Progress log
- `2026-11-16` — Built in the S47 sequential stack (DEC-5337). Lint, pyright, tsc, eslint and the WB-11 and route tests (85) clean; client regenerated. Partial: Brightwater Hale's catalogue file is canvas content in another shape, so its WB-11 words load through the reviewed import (content, not code); the linked-returns count needs a tax slot; agent display names wait on spec names. Gates and
  tests run once at the S47 end pass (build first, test last).
