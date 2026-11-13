---
id: TASK-7929
title: T-05-T57 rest: the xlsx export's grid widths and a person's cells filled
plan_key: T-05-T57
spec: SPEC-652
acceptance_criteria: [AC-6]
risk_zone: amber
status: in-review
branch: t05-t57-xlsx-styles
worktree: /Users/ayushkbhatia/Accrued/abacus-s42
created: 2026-11-13
updated: 2026-11-13
---

## Objective
Finish T-05-T57's styling partial: the exported workbook takes TXP-11's column widths and fills the cells a person wrote last, still byte-identical for identical data.

## Done
- `ExportSheet.widths` (px, from column A; Excel width = px / 7) and `ExportCell.human` (a solid pale-amber fill, no theme colour).
- Tax passes TXP-11's grid widths and, on the current version, the fields whose latest version is `human` (review's `latest_sources`); an earlier version's writers are not read back, so it has no fills.
- Test: widths on sheet 05, the fill only on the human cell, identical bytes.

## Partial
- Formula cells still carry no cached value (openpyxl writes none; Excel computes on open) — DEC-4925 keeps it.

## Progress log
- 2026-11-13: built in the S42 partials round; tests written, run at the partials end pass.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-4925 No cached values on exported formula cells | A cached value would be a second, unverified copy of the figure; Excel computes on open | no |
