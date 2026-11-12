---
id: TASK-7505
title: P-02-T05 migration search_documents and search_recents (0840)
plan_key: P-02-T05
spec: SPEC-000  # contract C15 v1; ADR-241; P-02 §4.2
acceptance_criteria: [AC-1]  # single head; RLS isolates two tenants on both tables; expand-only
risk_zone: red
status: in-review
branch: p02-t05-search-migration
worktree: /Users/ayushkbhatia/Accrued/abacus-s39
created: 2026-11-12
updated: 2026-11-12
---

## Objective
The expand-only migration for the firm search index: `search_documents` and `search_recents` with
forced RLS, CHECKs, GIN `tsv` and trigram indexes, platform ownership.

## Plan
- `backend/migrations/versions/0840_search_index.py` on 0832: both tables, forced RLS
  (`tenant_table`), CHECKs (groups, scope kinds, data classes, lengths, the scope columns a scope
  needs, identifier-shaped status codes, the saved-prompt tag), GIN on `tsv`, `gin_trgm_ops` on
  `title`, `identifiers_text`, `related_text`, freshness, client and group btrees; app role keeps
  the default privileges less TRUNCATE.
- `pg_trgm` and `btree_gin`: already created by `migrations/bootstrap.sql` (DEC-16); verified, not
  re-added.
- `platform/registry.py`: both tables owned by `platform`. `kernel/db/archive_guard.py` (PROTECTED,
  red): `search_documents` exempt, a rebuildable projection like `home_activity_items`.
- Tests: `backend/tests/integration/test_s39_migrations.py` (down/up, forced RLS, two-tenant
  isolation as the app role, CHECKs, indexes, no TIN/amount/text column, no guard);
  `tests/security/test_tenant_isolation.py` lists both tables.
- Rollback: the downgrade drops both tables; nothing reads them yet (flags off, routes 501).

## Partial
- The plan merges it in the Tue Apr 25, 2028 train after the window; in the solo build it merges in
  the S39 batch. Re-check `alembic heads` immediately before merging (another session may land on
  0832).

## Progress log
- `2026-11-12` — Migration built (DEC-4505). Tests run at the S39 end pass.
