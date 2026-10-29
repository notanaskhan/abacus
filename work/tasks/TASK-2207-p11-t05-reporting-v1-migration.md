---
id: TASK-2207
title: P-11-T05 migration reporting_v1 (expand-only)
spec: SPEC-520
acceptance_criteria: [AC-33, AC-27, AC-15, AC-16]
risk_zone: amber
status: todo
epic: P-11
plan_key: P-11-T05
branch: s17-p11-t05
worktree: /Users/ayushkbhatia/Accrued/abacus-s17
created: 2026-10-29
updated: 2026-10-29
---

## Objective
`generated_documents`, insert-only `generated_document_versions` (final requires `approval_ref`
and a human requester; agent requests are drafts), `generated_document_files`,
`generated_document_fields`, `generated_document_events`, `render_jobs`; RLS; registry entries.

Acceptance: "Every table is tenant-RLS, versions, files, fields and events reject UPDATE and DELETE
for every role, the mode CHECKs hold, and the single-head check passes."

## Plan (amber)
Migration `0430_reporting_v1.py` (reserved range 0430+; down_revision = main's head at build time,
re-chained at merge). Enums `generated_document_kind`, `render_mode`, `render_format` as CHECKs.
Forced RLS with the standard tenant policy on all six tables; the repo's insert-only trigger on
versions, files, fields and events; grants for the app role (INSERT and SELECT; `render_jobs` and
`generated_documents` UPDATE on named columns only); `reporting/registry.py` TABLES, INSERT_ONLY,
INSERT_COLUMNS, UPDATE_COLUMNS; the schema-check expectations. Tests:
`backend/tests/integration/reporting/test_p11t05_reporting_v1.py` (RLS isolation per table,
UPDATE/DELETE refused per role, `mode='final'` without approval or with an agent requester
refused, agent requester must be a draft with a run id). Rollback: the downgrade drops the six
tables (expand-only; nothing reads them yet).

## Progress log
- `2026-10-29` — Planned in P-11-T01.
