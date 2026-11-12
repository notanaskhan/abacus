---
id: TASK-7404
title: "T-05-T20: Migration 0830_tax_workbook_and_memo (expand-only): workpapers.kind tax_workbook, workpaper_cells formula columns, workpaper_versions engine_manifest and run link, preparer_memos, preparer_memo_versions (insert-only), preparer_memo_events (insert-only), planning_opportunities (open only)"
spec: SPEC-651
acceptance_criteria: [AC-1]  # formula cells only through record_value; memo versions refuse UPDATE and DELETE
risk_zone: amber
status: in-review
branch: s38-t05-t20
worktree: /Users/ayushkbhatia/Accrued/abacus-s38
created: 2026-11-12
updated: 2026-11-12
plan_key: T-05-T20
---

## Objective
The cell store accepts formula cells only through record_value, and memo versions refuse UPDATE
and DELETE.

## Plan (amber)
- Migration `0830_tax_workbook_and_memo` (on 0821; T-05 §4.2 M2): `workpapers_kind_check` admits
  `tax_workbook`; `workpaper_cells` + `formula`, `formula_inputs`, `engine_name`,
  `engine_version` (CHECK formula source ⇒ formula; engine pair), insert-granted; cells stay
  insert-only (0072), so every value is a new row through `review.api.record_value`;
  `workpaper_versions` + `engine_manifest`, `inputs_hash`. New `tax` tables `preparer_memos`
  (column-granted updates of the pointer, fingerprint, run and hash), `preparer_memo_versions` and
  `preparer_memo_events` (insert-only, trigger `preparer_memo_rows_immutable`),
  `planning_opportunities` (`status` open only). Agent versions name their run and person; an edit
  is a person's; adopted and approved events are a person's.
- Registries: `tax.registry` TABLES, INSERT_ONLY, INSERT_COLUMNS, UPDATE_COLUMNS;
  `workpapers.registry` INSERT_COLUMNS for the new columns.
- Tests: `tests/integration/test_s38_migrations.py` (down to 0821 and up, forced RLS, no DELETE,
  insert-only grants, the triggers, the formula CHECK, the kind, the human-only events, open only).
- Rollback: downgrade drops the four tables and the columns and restores the kind CHECK.

## Partial
- No ORM model or service reads the new tables yet (dark until the T-05 memo and workbook rows,
  T-05-T28 onward and T-05-T48).

## Progress log
- `2026-11-12` — Built (S38). Lint and types clean; migration tests run at the end pass.
