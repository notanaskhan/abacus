---
name: migration
description: How to change the database schema safely — numbering and renumbering, tenant tables, column grants, global tables behind SECURITY DEFINER functions, immutability triggers, the module registry, schema_check and the tests that prove grants. Use for any schema change.
---

# Migration pattern

Binding: ADR-014 (tenancy), ADR-004 (immutability), ADR-015 (never edit an applied migration), ADR-091 and ADR-135 (expand/contract; until the first real firm a breaking change may be one reversible migration), ADR-103 (table owners). The map of today's tables is `docs/architecture/data-model.md`.

## 1. Number and file

- Files are `backend/migrations/versions/NNNN_<slug>.py`, four digits, one linear chain. `revision = "NNNN"`, `down_revision` = the previous number, and the docstring ends with `Revision ID: NNNN` / `Revises: NNNN-1` (copy `script.py.mako` or the latest file).
- The number is the next free one **on `origin/main`**, not on your branch:
  `git fetch origin && git ls-tree --name-only origin/main backend/migrations/versions/ | sort | tail -1`
- One migration per PR. The docstring says what each table is for and names the task and decision (`(F-03-T22; DEC-07)`): it is the review record.
- **A migration already on `origin/main` is never edited** (the edit hook refuses; ADR-015). Fix it with a new migration. A migration only on your branch may still be edited.

## 2. Renumber on rebase

`make check-heads` fails with "multiple heads: rebase onto origin/main and renumber (P-38)" when `main` gained a migration with your number. After `git rebase origin/main`:

1. `git mv` your file to the next free number (step 1's command).
2. Update `revision`, `down_revision` (now `main`'s head) and the docstring's `Revision ID` / `Revises`.
3. Update every reference to the old number that your branch added: `# NNNN (TASK-…)` comments in `registry.py` and `schema_check.py`, the matching lines in `tests/integration/test_schema_check_db.py`, and any `migrate(..., "NNNN", down=True)` in tests.
4. `make check-heads`, then the migration's own tests. Put `[mig NNNN]` in the PR title (ADR-135).

## 3. A tenant table

Every new table gets SELECT, INSERT, UPDATE and DELETE for `abacus_app` by default (`bootstrap.sql` default privileges), so each migration takes away what the app must not have.

```python
from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

op.execute("""CREATE TABLE closes (
    tenant_id uuid NOT NULL, work_item_id uuid PRIMARY KEY, engagement_id uuid NOT NULL,
    period text NOT NULL CHECK (period ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'),
    created_at timestamptz NOT NULL DEFAULT abacus_now(),
    UNIQUE (tenant_id, engagement_id, period),
    FOREIGN KEY (tenant_id, engagement_id, work_item_id)
        REFERENCES work_items (tenant_id, engagement_id, id))""")
tenant_table(op, "closes")                       # RLS enabled + forced + tenant_isolation policy
op.execute("REVOKE UPDATE, DELETE ON closes FROM abacus_app")
insert_columns(op, "closes", ("tenant_id", "work_item_id", "engagement_id", "period"))
```

- `tenant_id uuid NOT NULL` and `tenant_table(op, name)` on every tenant table; never hand-write the policy.
- **Foreign keys carry `tenant_id`**: reference `(tenant_id, id)` (or `(tenant_id, engagement_id, id)` for work items) so a row can't point into another firm. The parent declares the matching `UNIQUE (tenant_id, …)`.
- **Insert columns:** `insert_columns(op, table, cols)` revokes table-wide INSERT and grants only the columns the app supplies; ids, sequence numbers, timestamps and server-set state stay out.
- **Update columns:** `REVOKE UPDATE, DELETE ON t FROM abacus_app`, then `GRANT UPDATE (col, …) ON t TO abacus_app` for exactly the columns a service changes (0068 `work_items`, 0100 `request_lists`).
- **Read-only to the app:** `REVOKE INSERT, UPDATE, DELETE ON t FROM abacus_app` (0088 `tenant_entitlements`: operators and the scenario loader write it).
- **Insert-only (ADR-004):** `insert_only(op, t)`. Evidence, ledger and review records also get a BEFORE UPDATE OR DELETE trigger and a BEFORE TRUNCATE trigger calling a function that raises (0092, 0094), listed in `schema_check.IMMUTABLE_TABLES` and in the expected map in `test_schema_check_db.py`.
- Business timestamps default to `abacus_now()` (the demo clock, 0085). Security and system times (audit `occurred_at`, sessions, tokens) use `clock_timestamp()`.
- CHECK every enum-like text column against its codes (status codes come from `docs/product/status-vocabulary.yaml`). Bound every free text length.
- Firm content (templates, programs, rules) never goes into a migration; it loads through an admin screen or import endpoint (AGENTS.md rule 16).

## 4. Register the table (same PR)

In the owning module's `backend/src/abacus/modules/<module>/registry.py`:

- `TABLES`: the table name. A table claimed by two modules fails `schema_check`, and so does a table on disk that no registry lists.
- `INSERT_ONLY` if the app may not update or delete it.
- `INSERT_COLUMNS[table]` and `UPDATE_COLUMNS[table]`: **the same column lists the migration grants**. `schema_check` reports any column the app can insert or update beyond them.

Tables outside the modules (kernel, gateway, eval tooling) use the `_PLATFORM_*` maps at the top of `backend/src/abacus_tools/quality/schema_check.py`.

## 5. Global tables and SECURITY DEFINER functions

A table shared across firms (no `tenant_id`, or one that must see every firm) is reached **only** through SECURITY DEFINER functions; the app holds no privilege on it.

```python
op.execute("REVOKE ALL ON plans FROM abacus_app")
op.execute("""CREATE FUNCTION email_template_current(p_key text, p_locale text) RETURNS TABLE (...)
    LANGUAGE sql STABLE SECURITY DEFINER
    SET search_path = pg_catalog, public, pg_temp
    AS $$ SELECT ... FROM public.email_templates t ... $$""")
op.execute("REVOKE ALL ON FUNCTION email_template_current(text, text) FROM PUBLIC")
op.execute("GRANT EXECUTE ON FUNCTION email_template_current(text, text) TO abacus_app")
```

- Pin `SET search_path = pg_catalog, public, pg_temp` and schema-qualify tables (`public.x`) in the body. Take the tenant from `current_setting('app.tenant_id')`, never from an argument the caller could forge, when the function acts for one firm.
- Revoke from PUBLIC; grant EXECUTE to `abacus_app` only. Operator-only functions are granted to `abacus_ops` instead and listed in `OPS_ONLY_FUNCTIONS`; owner-only ones in `OWNER_ONLY_FUNCTIONS`. `abacus_relay` and `abacus_identity` must never execute one.
- In `schema_check.py`, in the same PR, with a `# NNNN (TASK…)` comment:
  - `DEFINER_FUNCTIONS`: every new definer function name;
  - `GLOBAL_TABLES`: the table (the app has no privilege on it);
  - `NON_TENANT_TABLES`: the table (exempt from the tenant_id and RLS rules);
  - `_PLATFORM_TABLE_OWNERS` or a module `registry.py`: its owner.
- In `backend/tests/integration/test_schema_check_db.py`, add the same names to the expected sets (`test_ac20_the_migrated_database_has_exactly_the_reviewed_definer_functions`, and the `IMMUTABLE_TABLES` map for an immutable table). The test compares exact sets, so a function added without its line fails.

## 6. Prove it as the app role

Superuser and owner connections bypass grants and row-level security, so a test that runs as them passes while the app fails in production.

- **Every trigger and definer function needs a test that runs as `abacus_app`**: through `tenant_session(...)` (the `migrated_db` fixture points the engine at `app_url`) or an asyncpg connection to `migrated_db.app_url`. Seed with the superuser if you must; exercise as the app.
- Test the grants both ways: the app can insert and update the columns it needs, and is refused (`InsufficientPrivilegeError`) on one it must not touch, and on UPDATE or DELETE of an insert-only table.
- Cross-tenant: a second firm reads no row and can't insert one with the first firm's `tenant_id`.
- An integration test file that connects with asyncpg as the superuser must be added to the `DB-001` `exclude` list in `backend/src/abacus_tools/quality/banned_patterns.py`, with a one-line reason, the way the others are.

## 7. Destructive changes, backfills, timeouts

- Until the first non-synthetic firm is live, a rename or drop may be **one reversible migration**; `downgrade()` must restore the previous shape and the same PR updates seeds, the scenario loader and the generated client (ADR-135). From then on: expand, backfill, switch, contract across deploys (ADR-091).
- Every migration is reversible: `schema_check` migrates to head, down to base and up again.
- `migrations/env.py` connects as `abacus_owner` with `lock_timeout` 5s and `statement_timeout` 60s; one transaction per migration. Large backfills run as throttled Temporal workflows, not in the migration (ADR-091). Small, bounded backfills (0068's one assurance work item per engagement) may run in the migration.

## 8. Before you push

```
cd backend
uv run python -m abacus_tools.quality.schema_check        # tenant rules, grants, definers, owners
uv run python -m abacus_tools.codegen.security_tests      # a new tenant table adds an isolation case
uv run pytest tests/integration/test_schema_check_db.py tests/integration/test_<yours>.py
uv run python -m abacus_tools.quality.banned_patterns
make check-heads check-generated
```

A new tenant table changes the generated `tests/security/test_tenant_isolation.py`; regenerate it, never hand-edit it.
