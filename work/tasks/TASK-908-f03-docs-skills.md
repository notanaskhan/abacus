---
id: TASK-908
title: Docs and skills for migrations, backend modules, work-item kinds, the data model and contract vN+1 (F-03-T36)
spec: SPEC-047
acceptance_criteria: [AC-2]
risk_zone: amber
status: done
epic: F-03
plan_key: F-03-T36
branch: f03-t36-docs-skills
created: 2026-10-23
updated: 2026-10-23
---

## Objective
"A fresh Claude Code session can add a work-item kind and a migration using only the updated
skills and runbooks." Documents what is on `main` (migrations 0001 to 0101), read from the code.

## Plan
Docs and skills only; no code, migration, registry or generated-file change.
- `.claude/skills/migration/SKILL.md`: numbering from `origin/main`, renumber on rebase, tenant
  tables (`tenant_table`, `insert_columns`, column-level `GRANT UPDATE (...)`, default privileges),
  the registry, global tables behind SECURITY DEFINER functions (`DEFINER_FUNCTIONS`,
  `GLOBAL_TABLES`, `NON_TENANT_TABLES` with the matching expectations in
  `test_schema_check_db.py`), app-role tests for triggers and definers, DB-001 excludes,
  never editing a migration on `main`.
- `.claude/skills/backend-module/SKILL.md`: `MODULES`, `ROUTERS`, `registry.py`,
  `MODULE_DEPENDENCIES`, import-linter containers, the list envelope, registration slots, and
  the step list for adding a work-item kind.
- `docs/architecture/data-model.md` (new): ER diagram of the F-03 core from the migrated
  catalog's foreign keys; table purposes and rules; global tables and their definer functions.
- `docs/contracts/README.md`: runbook for shipping vN+1 with `abacus_tools.contracts`.
- Module READMEs: closes, tax, notices (subtype tables and kinds), platform (entitlements,
  capabilities, controls, search slot), organisations (tables owned), engagements (work items,
  kinds, lifecycle, gates; the 14 types).
- Rollback: revert the commit.

## Progress log
- 2026-10-23: written from the code on main (registries, schema_check, migrations 0068, 0069,
  0083, 0088, 0089, 0092, 0100, 0101, `abacus_tools.contracts`); FKs read from a freshly
  migrated database. validate_docs and banned_patterns green.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| Renumber-on-rebase and vN+1 are written as runbook sections in the migration skill and the contract register, not as `docs/runbooks/RB-nn` files | The RB index is for failure scenarios with alerts and rehearsals (ADR-098); these are routine procedures | no |
| No `make mig-next` / `mig-renumber` target is documented | Chapter 08 names them but they are not in the Makefile on main; the skill gives the git command instead | no |

## Gotchas and discoveries
- `abacus_tools.contracts --check` compares every snapshot on disk with the current models, so a
  breaking change can only ship as new model names beside the old ones; retiring vN means
  deleting `vN.json` with the old models.
- `bootstrap.sql` grants the app SELECT, INSERT, UPDATE and DELETE on every new table by default;
  each migration must revoke what the app should not have.
