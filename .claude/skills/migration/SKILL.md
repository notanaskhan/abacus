---
name: migration
description: How to change the database schema safely — Alembic, expand-then-contract, row-level security, timeouts, backfills. Use for any schema change.
---

# Migration pattern

1. Create a **new** revision; never edit an applied one (ADR-015).
2. New tables: `tenant_id NOT NULL`, enable and force row-level security, add the policy, grant only needed privileges to the application role (ADR-014).
3. Immutable tables: no UPDATE or DELETE privilege for the application role (ADR-004).
4. Destructive changes use expand-then-contract across deploys (ADR-091).
5. Indexes created concurrently; lock and statement timeouts set.
6. Large backfills run as throttled Temporal workflows, not in the migration (ADR-091).
7. Run `make check`: upgrade and downgrade against real Postgres, migration linter, schema check.
