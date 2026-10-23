---
id: TASK-945
title: Migration 0109 trust_kit_v1 — citations, citation_events, evidence pages, PII scans, regions and reveals, derivations (P-03-T04)
spec: SPEC-322
acceptance_criteria: [AC-15, AC-16, AC-17, AC-18, AC-19, AC-20]
risk_zone: red
status: done
epic: P-03
plan_key: P-03-T04
branch: s5-trust-kit
created: 2026-10-23
updated: 2026-10-23
---

## Objective
The trust kit's tables, insert-only and tenant-scoped, ready for the C4 implementation.

## Plan (red zone)
- **Migration:** `backend/migrations/versions/0109_trust_kit_v1.py` — tables `evidence_derivations`, `citations`, `citation_events`, `evidence_pages`, `pii_scan_runs`, `pii_regions`, `pii_reveals`; view `citation_current` (security_invoker); trigger `trust_kit_immutable`; `derivation_id` on `upload_extractions` and `upload_previews`, `mask_version` on previews, their unique indexes rebuilt NULLS NOT DISTINCT. RLS through `tenant_table`; app role gets INSERT and SELECT only.
- **Registries:** evidence registry TABLES and INSERT_ONLY; schema_check IMMUTABLE_TABLES and its expectation in `tests/integration/test_schema_check_db.py`.
- **Tests:** `tests/integration/test_trust_kit_schema.py` (unverified citation needs a reason; update and delete refused; relink by a person only; `citation_current` shows `relinked`); full schema_check.
- **Rollback:** `alembic downgrade 0108` drops the tables, view, trigger function and added columns, and restores the old unique indexes.

## Progress log
- 2026-10-23: built; schema_check clean; integration tests pass as the app role.
