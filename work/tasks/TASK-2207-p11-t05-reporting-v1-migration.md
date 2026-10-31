---
id: TASK-2207
title: P-11-T05 migration reporting_v1 (expand-only)
spec: SPEC-520
acceptance_criteria: [AC-33, AC-27, AC-15, AC-16]
risk_zone: amber
status: done
epic: P-11
plan_key: P-11-T05
branch: s17-p11-t05
worktree: /Users/ayushkbhatia/Accrued/abacus-s17
created: 2026-10-29
updated: 2026-11-01
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
- `2026-10-29` — Built on `s17-p11-t05` (stacked on T04): `migrations/versions/0430_reporting_v1.py`
  (down_revision 0321, main's head; re-chain at the merge after S15's 0370s and S16's 0400s),
  `reporting/registry.py`, `tests/integration/test_p11t05_reporting_schema.py` (round trip,
  single head, forced RLS and schema_check, insert-only refusals for every role incl. the
  superuser via the trigger, tenant isolation, final needs a person and an approval on this
  content hash, agent drafts name their run, evidence xor sample, out-of-date keys, render-job
  update columns), banned-pattern exclusions for the test. Run at the S17 end review.
- 2026-11-01: merged to main in #747 (23d9fbca7).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| An approval's `content_hash` must equal the version's (CHECK) | AC-15 in the database, not only the service | no |
| No trigger on the requester's identity (as envelopes have) | the RenderWorkflow records versions as the system on a person's behalf; the CHECKs hold the shape | no |
| `generated_document_fields.occurrence` | a variable may appear more than once on a page | no |
| No FK from files to `evidence_versions` | evidence is red and its own module's table; the service asserts the fingerprint (AC-25) | no |
