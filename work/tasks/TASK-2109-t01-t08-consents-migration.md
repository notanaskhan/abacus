---
id: TASK-2109
title: T-01-T08 Migration consents (organisations)
spec: SPEC-501
acceptance_criteria: [AC-15, AC-16]
risk_zone: red
status: in-review
epic: T-01
plan_key: T-01-T08
branch: s16-t01-t08
created: 2026-10-29
updated: 2026-10-29
---

## Objective
Migration 0402: `consent_sets`, `consents`, `consent_signers`, insert-only `consent_events` with
forced RLS, CHECKs and the declined-purpose partial unique index (T-01 §4.2).

## Plan (red)
- `backend/migrations/versions/0402_consents.py` (revises 0401).
- `organisations/registry.py`; `schema_check.IMMUTABLE_TABLES`; pins in `test_schema_check_db.py`;
  regenerated isolation suite; DB-001/TENANT-001 exclusions for the 0400–0402 schema tests.
- Rollback: `alembic downgrade 0401`.

## Acceptance
`backend/tests/integration/backfill/test_t01t08_consents.py`; generated tenancy cases.

## Progress log
- 2026-10-29: built (S16 block; tests run at the batch's end review). DEC-1159.
