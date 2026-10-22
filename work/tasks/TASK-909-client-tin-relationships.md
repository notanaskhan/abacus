---
id: TASK-909
title: Sealed TIN columns, client descriptor, entity relationships and trigram name search (P-07-T07)
spec: SPEC-321
acceptance_criteria: [AC-2]
risk_zone: red
status: done
epic: P-07
plan_key: P-07-T07
branch: p07-t07-client-tin-relationships
created: 2026-10-23
updated: 2026-10-23
---

## Objective
"The single-head check passes, RLS isolates two tenants on entity_relationships, and a schema test finds no plaintext tin, ssn or ein column" (P-07-T07; DEC-52, DEC-16; P-07 §4.2 M1).

## Plan
- Migration `0103_client_tin_relationships`:
  - TIN columns on `client_entities`, with a whole-set CHECK and a partial unique fingerprint index;
  - `clients.descriptor`;
  - `entity_relationships` under RLS (app inserts and ends rows, never deletes them);
  - a generated `contacts.normalised_name`;
  - GIN trigram indexes `(tenant_id, normalised_name gin_trgm_ops)` on clients, entities and contacts.
- `bootstrap.sql` (protected) creates `pg_trgm` and `btree_gin`. The owner role has no CREATE on the database, so a migration can't create them. 0103 fails clearly without them.
- schema_check: a new rule refuses any column named `tin`, `ssn`, `ein` or `itin`, or ending `_tin`/`_ssn`/`_ein`/`_itin`.
- Organisations registry: the new table and column grants.
- Rollback: downgrade 0103 drops the indexes, table and columns. The extensions stay; they are harmless.

## What changed
- As planned. `tin_status = 'on_file'` holds exactly when a sealed TIN, its last four digits, kind and fingerprint are all present.
- Tests:
  - `test_schema_check_db.py` covers the plaintext-TIN rule (flags six names, passes the sealed columns and lookalikes such as `latin`);
  - `test_client_tin_relationships.py` covers app-role grants, the whole-TIN CHECK and the once-per-firm fingerprint;
  - the generated tenant-isolation case covers `entity_relationships`;
  - the full `schema_check` (up, down, up) passes.

## Hosted databases
A hosted database needs `bootstrap.sql` re-applied by its admin (or `CREATE EXTENSION pg_trgm; CREATE EXTENSION btree_gin;`) before 0103 runs. No pipeline runs migrations on merge today.

## Not done
- Sealing, masking and reveal: P-07-T10.
- `normalised_name` already existed on `client_entities` (0035), so it was not re-added.

## Progress log
- 2026-10-23: the tests above pass locally.
