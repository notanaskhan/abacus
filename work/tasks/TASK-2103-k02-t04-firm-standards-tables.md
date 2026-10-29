---
id: TASK-2103
title: K-02-T04 Methodology tenant migration for firm standards and threshold policies
spec: SPEC-500
acceptance_criteria: [AC-11, AC-12]
risk_zone: amber
status: in-review
epic: K-02
plan_key: K-02-T04
branch: s16-k02-t04
created: 2026-10-29
updated: 2026-10-29
---

## Objective
Migration 0401: `firm_standards`, `threshold_policies` and their version tables with forced RLS,
one draft per standard, monotonic versions, a freeze trigger and the human-only publish CHECK
(K-02 §4.2 M-B).

Acceptance (backlog row): "Generated tenancy tests pass and trigger tests show a published version
cannot change and a second draft is refused."

## Plan (amber)
- `backend/migrations/versions/0401_firm_standards.py` (revises 0400).
- `methodology/registry.py`: TABLES, INSERT_COLUMNS, UPDATE_COLUMNS; the APP_UPDATE_COLUMNS pin in
  `tests/integration/test_schema_check_db.py`; regenerated `tests/security/test_tenant_isolation.py`.
- Status codes: landed in T02 (DEC-1151); asserted here.
- Rollback: `alembic downgrade 0400`.

## Acceptance
| Check | Test |
|---|---|
| Tenancy | generated `test_tenant_isolation.py` (four new tables) |
| Published version frozen | `test_ac11_a_published_version_cannot_change` |
| Second draft refused | `test_ac11_a_second_draft_is_refused` |
| Version numbering, no delete, discard | `test_ac11_versions_*`, `test_ac11_nothing_is_deleted_*` |
| Human-only publish | `test_us33_publishing_is_a_persons` |
| Status registry | `test_ac12_*` |

All in `backend/tests/integration/backfill/test_k02t04_firm_standards.py`.

## Progress log
- 2026-10-29: built (S16 block; tests written first, run at the batch's end review). DEC-1153.
