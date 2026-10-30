---
id: TASK-2102
title: K-02-T03 Global reference-set tables migration
spec: SPEC-500
acceptance_criteria: [AC-8, AC-9, AC-10]
risk_zone: red
status: in-review
epic: K-02
plan_key: K-02-T03
branch: s16-k02-t03
created: 2026-10-29
updated: 2026-10-29
---

## Objective
Migration 0400: the global reference-set tables, the app's published-only readers, the operators'
owner-only writers and `standards_sets_apply` (K-02 §4.2 M-A; ADR-300).

Acceptance (backlog row): "schema_check passes up/down/up and abacus_app can read published
versions only through the readers and can never write or see a draft, and publishing a
standards_sets version adds its codes to K-01's standards_sets while an existing code is never
deleted."

## Plan (red)
- `backend/migrations/versions/0400_reference_sets.py` (revises 0295; re-chain at merge).
- `schema_check.py`: `NON_TENANT_TABLES`, `GLOBAL_TABLES`, `IMMUTABLE_TABLES`,
  `DEFINER_FUNCTIONS`, `OWNER_ONLY_FUNCTIONS`; `platform/registry.py` `TABLES`; the exact-set pins
  in `tests/integration/test_schema_check_db.py`.
- Contract `StandardsSetRow.code` pattern and label length aligned with 0180's CHECKs.
- `.claude/skills/migration/SKILL.md` §5a recipe.
- Rollback: `alembic downgrade 0295` drops the functions and tables (no other table references them).

## Acceptance
| Check | Test |
|---|---|
| up/down/up and schema_check | `test_ac10_the_migration_passes_up_down_up` |
| App: no table privilege, no writer, drafts invisible | `test_ac8_*`, `test_ac10_the_operators_functions_are_owner_only`, `test_us11_us12_*` |
| Two people; resolution; frozen; one draft | `test_us11_us12_*`, `test_us12_*`, `test_ac9_*` |
| Standards sets added, never deleted; issuer refused | `test_us14_*` |

All in `backend/tests/integration/backfill/test_k02t03_reference_sets.py`.

## Progress log
- 2026-10-29: built (S16 block; tests written first, run at the batch's end review). DEC-1152.
