---
id: TASK-3255
title: P-11-T24 migration 0666 ocr_v1 (OCR runs, extracted fields and tables)
spec: SPEC-000  # row; P-11 §4.2 migration 3
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: P-11
plan_key: P-11-T24
branch: s27-p11-t24
worktree: /Users/ayushkbhatia/Accrued/abacus-s27
created: 2026-11-04
updated: 2026-11-04
---

## Objective
"Every new table is tenant-RLS and insert-only for all roles, sealed values are never selected by
list queries, and the single-head check passes."

## Plan (red)
- Migration 0666 on 0665 (expand-only): `ocr_runs`, `extracted_fields` (TIN sealed with last4,
  CHECK), `extracted_tables`, `extracted_table_cells`; one source per row (0109's rule); all
  insert-only with `trust_kit_immutable`. `evidence_pages` gains `text_source`, `ocr_run_id`,
  `mean_confidence`, `low_conf_words` (plain column GRANT so 0109's grants stay);
  `document_classifications` gains `form_map_version` (`corrected` exists from 0404).
  `upload_extractions` already keys on `extractor_version` (0043).
- Evidence registry (TABLES, INSERT_ONLY, INSERT_COLUMNS); `IMMUTABLE_TABLES`; tenant list.
- Refusal reasons follow P-11 AC7.2's gate order, with `boundary_basis` for the boundary check.
- Tests: `tests/integration/test_p11t24_ocr_v1_migration.py`.
- Rollback: the downgrade drops the tables and columns.

## Progress log
- 2026-11-04: built. Found while writing it: `insert_columns` revokes a table's INSERT, and
  PostgreSQL then revokes every column grant too; 0664's call on `eqr_concurrences` would have
  dropped 0077's grants. Fixed in a fixup for A-07-T07 (full column list). Second time this kind
  of grant bug appears (S26: control_exceptions grants): candidate lint.

## Decisions made during this task
DEC-2235.
