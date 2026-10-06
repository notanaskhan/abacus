---
id: TASK-005
title: "Kernel: config, logging, tenant sessions with row-level security, migrations"
spec: SPEC-000
acceptance_criteria: [AC-5, AC-13, AC-20]
risk_zone: red
status: done
branch: task-005-kernel-db
worktree:
created: 2026-10-06
updated: 2026-10-06
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: do not write code until the plan is marked approved.
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
Build the kernel foundations every module depends on — settings, data classification, structured logging that refuses Restricted data, the owner and application database roles, `tenant_session(ctx)` enforced by forced row-level security, Alembic with timeouts and reversibility, insert-only tables, and the real `schema_check` — so that tenant isolation holds at the database even if application code is wrong.

## Scope
**In**
- `abacus.kernel.config` — typed settings (pydantic-settings)
- `abacus.kernel.classification` — the ADR-031 tag mechanism and a gate that every Pydantic field carries one
- `abacus.kernel.logging` — structlog JSON logging helper that refuses Restricted values (ADR-022, ADR-031)
- `abacus.kernel.db` *(red, protected)* — engine, `TenantContext`, `tenant_session`, RLS and insert-only helpers for migrations
- Database bootstrap SQL (roles), Alembic environment, migration `0001_baseline`
- `abacus_tools.quality.schema_check` — the real check, replacing TASK-002's guard
- Tests from an independent session (contract below)

**Out**
- Product tables (`firms`, `memberships`, … — TASK-007 onwards); building `TenantContext` from a membership (TASK-007)
- Unit of work, commits, audit events, outbox (TASK-006). `tenant_session` never commits (see design)
- Migration linter for unsafe operations (ADR-015) — Q3
- Tracing and error tracking (TASK-013)

## Context to load
- ADR-014 (RLS), ADR-015 (SQLAlchemy, Alembic), ADR-022 (logging), ADR-031 (classification), ADR-091 (migrations), ADR-095, ADR-101
- `docker-compose.yml`, `backend/tests/integration/conftest.py`, `Makefile` (`migrate`, `check`)

## Plan
- [x] Plan approved by human (founder, 2026-10-06: "approved") — **red: founder reviews the diff line by line before merge**
- [x] Approval file `work/approvals/TASK-005.yaml` written by the agent at the founder's instruction (2026-10-06)
- Approved by founder: paths under *Approval file text*, expires 2026-10-27
- [x] Q1–Q4 answered: all recommendations approved (2026-10-06)

### Design (for founder review)

**1. Roles** — two roles per database, created by a bootstrap script, not by migrations (Q1):
| Role | Login | Owns tables | Bypasses RLS | Used by |
|---|---|---|---|---|
| `abacus_owner` | yes | yes | no (but RLS is `FORCE`d, so owner is subject to it too) | Alembic only |
| `abacus_app` | yes | no | no (`NOBYPASSRLS`, `NOSUPERUSER`, `NOCREATEROLE`, `NOCREATEDB`) | API and worker |

`backend/migrations/bootstrap.sql` creates both roles and the database grants, idempotently. Locally it runs from the compose `db` service's init directory and from the testcontainers fixture; in staging it is run once by the operator or Terraform (TASK-014). `ALTER DEFAULT PRIVILEGES FOR ROLE abacus_owner` grants `abacus_app` `SELECT, INSERT, UPDATE, DELETE` on new tables; insert-only tables revoke `UPDATE, DELETE` explicitly (below).

**2. Row-level security** — every tenant table, in the migration that creates it, calls `abacus.kernel.db.migration.tenant_table(op, "<table>")`, which emits:
```sql
ALTER TABLE <t> ENABLE ROW LEVEL SECURITY;
ALTER TABLE <t> FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON <t>
  USING      (tenant_id = current_setting('app.tenant_id', true)::uuid)
  WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
```
`current_setting(..., true)` returns NULL when no tenant is set, so a session without a tenant sees **no rows and can insert none** (fails closed). `insert_only(op, "<table>")` revokes `UPDATE, DELETE` from `abacus_app` (AC-13 mechanism; evidence and ledger tables use it in TASK-009/010).

**3. `tenant_session(ctx)`** — the only way product code touches the database:
```python
@dataclass(frozen=True)
class TenantContext:
    tenant_id: UUID
    actor_kind: Literal["human", "agent", "system"]
    actor_id: str

@asynccontextmanager
async def tenant_session(ctx: TenantContext) -> AsyncIterator[AsyncSession]:
    async with _engine().connect() as conn:          # abacus_app role
        async with conn.begin() as tx:
            await conn.execute(text("SELECT set_config('app.tenant_id', :t, true)"),
                               {"t": str(ctx.tenant_id)})          # transaction-local
            yield AsyncSession(bind=conn, ...)
            await tx.rollback()                     # reads only; writes commit via the UoW (TASK-006)
```
- `set_config(..., true)` is transaction-local: the tenant can never leak to the next user of a pooled connection.
- `tenant_session` never commits. TASK-006's unit of work opens the same kind of transaction and is the only place that commits (UOW-001 already enforces this).
- The engine is created lazily from settings with `statement_timeout` and `application_name`; `abacus_owner` credentials are never available to the app.

**4. Alembic** — `backend/alembic.ini`, async `backend/migrations/env.py` connecting as `abacus_owner` (`ABACUS_MIGRATIONS_DATABASE_URL`) with `lock_timeout = 5s` and `statement_timeout = 60s` per migration session (ADR-091); revisions `NNNN_slug`. `0001_baseline` creates extensions `vector` and `pgcrypto` only; product tables start in TASK-007. `make migrate` is unchanged.

**5. `schema_check`** (real) — `python -m abacus_tools.quality.schema_check` starts Postgres from the compose image (testcontainers), runs `bootstrap.sql`, migrates up to head, **down to base and up again** (ADR-015 reversibility), then inspects the catalog and fails on any of:
- a table in `public` (other than an explicit allowlist in `schema_check.py`, starting with `alembic_version`) without a `tenant_id uuid NOT NULL`, without `relrowsecurity` **and** `relforcerowsecurity`, or without a `tenant_isolation` policy referencing `app.tenant_id`
- a table owned by anyone but `abacus_owner`; `abacus_app` with `BYPASSRLS`, `SUPERUSER` or ownership of anything
- a table listed as insert-only (declared in `schema_check.py`) on which `abacus_app` has `UPDATE` or `DELETE`

It replaces TASK-002's "no migrations yet" guard and the `check_orm` stop-gap.

**6. Classification (ADR-031)** — `abacus.kernel.classification`: `Classification = Literal["restricted", "confidential", "internal", "public"]` and `classified(level, **field_kwargs)` returning `Field(json_schema_extra={"cls": level}, ...)`, matching ADR-031's example. Gate: a unit test imports every module under `abacus` and fails if any `BaseModel` field lacks `cls` (no models yet, so it passes vacuously and binds TASK-007 onwards). This delivers the classification-tag check TASK-002 deferred to SPEC-000.

**7. Logging (ADR-022)** — `abacus.kernel.logging.get_logger(name)` returns a structlog logger emitting JSON with event name, level, timestamp; it **raises** if passed a Pydantic model containing a `restricted` field, and serialises other models by their non-restricted fields only. Values must be primitives, UUIDs, dates or classified models — arbitrary objects are refused (no accidental `repr` of client data).

**8. Settings** — `abacus.kernel.config.Settings` (pydantic-settings, prefix `ABACUS_`): `environment` (`local`/`test`/`staging`/`production`), `database_url`, `migrations_database_url` (`SecretStr`), `s3_*`, `temporal_target`. Local defaults point at `docker compose` (port 55432, local passwords); outside `local`/`test`, every connection setting must be set explicitly or startup fails.

### Steps
1. [x] Protect first: add `backend/migrations/env.py`, `backend/migrations/bootstrap.sql`, `backend/alembic.ini` to the hook, CODEOWNERS and protected-paths.md (Q4).
2. [x] Bootstrap SQL; mount into compose `db` init; testcontainers fixture runs it.
3. [x] `kernel/config.py`, `kernel/classification.py`, `kernel/logging.py`.
4. [x] `kernel/db/` — engine, `TenantContext`, `tenant_session`, `migration.tenant_table`, `migration.insert_only`.
5. [x] Alembic: `alembic.ini`, `migrations/env.py`, `0001_baseline`.
6. [x] `schema_check` rewrite; `check_orm` removed.
7. [x] Independent tests from the contract; `make check` locally and in CI; gate-break: a probe table without `FORCE`, without a policy, with `UPDATE` granted on an insert-only table, and an app role with `BYPASSRLS` each fail `schema_check`.

### Interface contract (tests written independently — ADR-078)
- `TenantContext(tenant_id: UUID, actor_kind: "human"|"agent"|"system", actor_id: str)`, frozen.
- Test fixture contract (implementer provides in `backend/tests/integration/conftest.py`): session-scoped `migrated_db` yielding `MigratedDatabase(owner_url: str, app_url: str)` — SQLAlchemy async URLs (`postgresql+asyncpg://…`) for `abacus_owner` and `abacus_app` on a fresh Postgres (compose image) with `bootstrap.sql` applied and migrated to head — and with `abacus.kernel.db.configure_engine(app_url)` already called, so `tenant_session` uses it.
- `abacus.kernel.db.configure_engine(url: str) -> None` replaces the process engine (startup and tests); `dispose_engine()` closes it.
- `tenant_session(ctx) -> AsyncContextManager[AsyncSession]` (from `abacus.kernel.db`), connected as `abacus_app`, with `current_setting('app.tenant_id')` = `str(ctx.tenant_id)` inside, and the setting absent on the same pooled connection after exit. Changes made inside are rolled back on exit.
- `abacus.kernel.db.migration.tenant_table(op, table: str)` and `insert_only(op, table: str)` emit exactly the SQL in Design §2 (tests may call them with a recording `op` stub and also apply them to a real table).
- Behaviour to prove against a real Postgres (testcontainers, bootstrap applied, migrated to head), using a probe tenant table created through `tenant_table` in the test:
  - (AC-5) rows of tenant B are invisible through `tenant_session` for tenant A — `SELECT`, `UPDATE … WHERE id = <B's id>` affects 0 rows, `DELETE` affects 0 rows
  - inserting a row with another tenant's `tenant_id` fails (`WITH CHECK`)
  - with no tenant set (raw `abacus_app` connection), `SELECT` returns 0 rows and `INSERT` fails
  - `abacus_app` cannot `ALTER TABLE … DISABLE ROW LEVEL SECURITY`, `NO FORCE`, `DROP POLICY`, or `SET ROLE abacus_owner`
  - the tenant setting does not survive to the next checkout of the same pooled connection
  - (AC-13 mechanism) after `insert_only`, `UPDATE` and `DELETE` by `abacus_app` fail; `INSERT` and `SELECT` work
- `Settings`: local defaults; `environment="staging"` without `database_url` raises; secrets are `SecretStr` and never appear in `repr`.
- Classification gate: a `BaseModel` with an unclassified field fails it; `classified("restricted")` sets `json_schema_extra={"cls": "restricted"}`.
- Logging: emits one JSON object per event with keys `event`, `level`, `timestamp` and the kwargs; raises `ValueError` for a model with a restricted field or for an arbitrary object value.
- `schema_check.check(dsn_owner: str, dsn_app: str) -> list[str]` against a migrated database; messages `"<table>: <problem>"`, sorted; `main()` provisions its own container and exits 0/1.

#### Contract revision 1 (2026-10-06, from the stage 4 security review)
- **Pool leak:** `tenant_session` runs `RESET app.tenant_id` before `set_config(..., true)`, so a session-level `SET app.tenant_id` / `set_config(..., false)` left on a pooled connection by earlier code can never carry into the next session. New banned pattern **TENANT-001**: a string literal containing `app.tenant_id` outside `src/abacus/kernel/db/*`, `src/abacus_tools/quality/schema_check.py` and the two tenancy/schema integration test files.
- **Policies, exact:** `schema_check` requires, per tenant table, **exactly one** policy: named `tenant_isolation`, `PERMISSIVE`, command `ALL`, roles `{public}`, with `qual` and `with_check` **identical** to those Postgres stores for the canonical `tenant_table` SQL (computed by applying `tenant_table` to a scratch table in a rolled-back transaction). Messages: `<t>: policy <name> is not the canonical tenant_isolation policy`, `<t>: has <n> policies; exactly one (tenant_isolation) is allowed`.
- **Views:** materialized views and foreign tables readable by `abacus_app` fail (`<name>: <materialized view|foreign table> is readable by abacus_app; row-level security does not apply`); plain views must be `security_invoker` (`<name>: view is not security_invoker`). Allowlist: none.
- **Large objects:** `bootstrap.sql` revokes `EXECUTE` on every `pg_catalog` large-object function (`lo_*`, `loread`, `lowrite`) from `PUBLIC`; `schema_check` reports `abacus_app: can execute <function>` for any it can still execute.
- **Functions:** default privileges revoke `EXECUTE` on the owner's future functions from `PUBLIC`; `CONNECT`/`TEMPORARY` on `postgres` and `template1` revoked from `PUBLIC`.
- **Logging:** models with **unclassified** fields (at any depth) are refused like Restricted ones (`ValueError`).
- **Settings:** validation errors never include input values (`hide_input_in_errors`).

### Approval file text
```yaml
task: TASK-005
approved_by: founder
expires: 2026-10-27
paths:
  - .claude/hooks/_protected.py
  - .github/CODEOWNERS
  - docs/architecture/protected-paths.md
  - docker-compose.yml
  - backend/pyproject.toml
  - backend/uv.lock
  - backend/alembic.ini
  - backend/migrations/env.py
  - backend/migrations/bootstrap.sql
  - backend/src/abacus/kernel/db/**
  - backend/src/abacus_tools/quality/schema_check.py
  - backend/tests/unit/quality/test_schema_check.py
reason: TASK-005 — kernel database, roles, row-level security, migrations, schema check
```
New migration files (`backend/migrations/versions/*`) need no approval while new; they become immutable once they exist (hook).

## Definition of done
- [ ] All listed ACs have passing tests that reference them (AC-5 and AC-13 at the mechanism level; product tables prove them again later)
- [ ] Type check passes
- [ ] Lint and format pass
- [ ] Architecture and dependency rules pass
- [ ] Full test suite passes; no tests skipped, weakened or deleted
- [ ] Security scan passes; no secrets committed
- [ ] No new dependencies, or each one approved and listed below
- [ ] Every query is tenant-scoped — enforced by RLS and `schema_check` from here on
- [ ] AI calls — n/a
- [ ] Module README and relevant docs updated (kernel README)
- [ ] Decisions below reviewed; ADR raised where needed
- [ ] Both CI jobs pass on the PR; reviewed line by line by the founder

## New dependencies
| Package | Version | Why | Approved by |
|---|---|---|---|
| sqlalchemy (asyncio), alembic, pydantic, pydantic-settings, structlog | pinned in `uv.lock` | ADR-014/015/022 | Allowlist (approved) |

## Progress log
- `2026-10-06` — PRs #3 and #4 merged at founder instruction. Design drafted for founder review (red task). No code.

- `2026-10-06` — Implemented. Protected `alembic.ini`, `migrations/env.py`, `migrations/bootstrap.sql` first. Independent tests (Sonnet, from the contract): 148 across kernel unit tests, tenancy integration (28) and schema-check databases (21). `make check` exit 0: 1,403 tests, coverage 97 %, `schema_check` real and passing (2.4 s).
  - **Bugs found by the independent tests, fixed in code:** (1) logger let Restricted data through a nested model — now refused at any depth; (2) on a reused pooled connection `current_setting` reads `''`, and `''::uuid` raised instead of returning no rows — policy now `NULLIF(current_setting('app.tenant_id', true), '')::uuid` (contract SQL updated); (3) `Settings` fields were unclassified — now classified, so the gate stays literal.
  - **Found while building:** pgvector isn't a trusted extension, so `bootstrap.sql` (admin) creates it and `0001_baseline` only verifies it (design §4 said the migration would create it); default privileges let `abacus_app` write `alembic_version` (forge migration state) — `0001` revokes it and `schema_check` now fails any app privilege on a non-tenant table, and any object (relation, function, type, schema) the app role owns.
  - **Design deviation:** `classified(level)` is used inside `Annotated[...]` rather than as a default value — as a default, a `-> Any` helper made type checkers treat required fields as optional. Same tag, same place (`json_schema_extra={"cls": ...}`).
  - `tenant_session` relies on the pool's rollback-on-return instead of calling `rollback()` (UOW-001 forbids rollback outside the unit of work).
  - Founder-approved exclusions (approval file extended at founder instruction): SQL-001 for `kernel/db/migration.py` (DDL can't bind identifiers; names validated); DB-001 for `schema_check.py`, `test_tenancy.py`, `test_schema_check_db.py`. S106/T20 scoped to `schema_check.py` in pyproject.
  - Local DB volume recreated so `bootstrap.sql` runs (compose init only runs on an empty volume).
  - Independent author's test bugs (fixed by them): keyword-less assertion that could never pass; `alembic_version` fixture without the 0001 revoke.

- `2026-10-06` — Stage 4 reviews (Sonnet), both CHANGES REQUESTED. Fixed via *Contract revision 1*:
  - **Security:** session-level `SET app.tenant_id` survived pool rollback and leaked to the next checkout (reproduced by reviewer) — `tenant_session` now `RESET`s tenant and actor settings first, and banned pattern TENANT-001 confines the setting to `kernel.db`; `schema_check` policy check was a substring test (`OR true`, extra permissive policy, wrong role all passed) — now exactly one canonical policy, derived by applying `tenant_table` to a temporary table; materialized views/foreign tables (no RLS) and non-`security_invoker` views now fail; large-object functions (not tenant-scoped) revoked from PUBLIC in `bootstrap.sql` and checked; TRUNCATE/TRIGGER on tenant tables checked; default `EXECUTE` on owner functions revoked; `CONNECT`/`TEMPORARY` on `postgres`/`template1` revoked; logger refuses unclassified fields at any depth; settings errors hide input (secrets); S3 keys required outside local.
  - **Architecture blockers:** `session.commit()` was silently inert (conservative savepoint join) — now explicit `join_transaction_mode="rollback_only"`, documented; TASK-006 must own its transaction (noted for its plan). Migrations ran in one transaction because the `SET` timeouts opened one first — timeouts now arrive as connection parameters; verified a failing third migration leaves the second applied, and timeouts are visible inside migrations.
  - Also: actor kind/id set per transaction (`app.actor_kind`, `app.actor_id`) for the audit trail; `bootstrap.sql` grants the admin membership in `abacus_owner` when not a superuser (managed Postgres) and was verified idempotent; `bootstrap*.sql` and `script.py.mako` protected; `path_separator` in `alembic.ini`; stray `*.py-E` sed backups removed.
  - Logged deviation: design §4 listed `pgcrypto`; not created — `gen_random_uuid()` is built into Postgres 13+, nothing needs it.
  - `INSERT_ONLY_TABLES` in `schema_check` is declared separately from `insert_only()` calls; TASK-009 must add each table to both (noted for its plan).
  - **Open:** tests for TENANT-001 need `backend/tests/unit/quality/test_banned_patterns.py`, which is protected and not in this task's approval — asked the founder.

- `2026-10-06` — Tests for the review fixes written independently (round 3). They found two more issues: (1) `schema_check` crashed on views — asyncpg returns Postgres `"char"` (`relkind`) as bytes — fixed; (2) an apparent per-migration-transaction failure, traced (SQL log) to the test author's revision generator putting the second statement at module level via `textwrap.dedent` — their bug, fixed by them; my env.py fix stands (hand-written revisions prove it). Also found and removed stale `.pyc` files from my own probe migrations in `migrations/versions/__pycache__`, which Alembic had loaded as revisions. Founder approved `test_banned_patterns.py` for TENANT-001 tests (21 cases). Two more exclusions of the approved kind: DB-001 for `test_migrations_env.py`, UOW-001 for `test_tenancy.py` (proves `session.commit()` is inert). `make check` exit 0: 1,432 unit + 95 integration, coverage 97 %.

- `2026-10-06` — PR #5 merged to `main` (rebase) after green CI, at founder instruction; approval file deleted. Done.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| `tenant_session` never commits; only the unit of work does | One commit point, with audit and outbox (ADR-007/018); UOW-001 already enforces it | no |
| `set_config(..., true)` (transaction-local) | Tenant can't leak across pooled connections | no |
| `current_setting(..., true)` in policies | No tenant set ⇒ NULL ⇒ no rows, no inserts (fail closed) | no |
| RLS `FORCE`d | The owner is subject to RLS too; a migration bug can't silently read across tenants | no |
| Roles from a bootstrap script, not migrations | Migrations never need `CREATEROLE`; managed Postgres provisions roles separately | Q1 |

## Gotchas and discoveries
- `schema_check` now needs Docker (it starts Postgres); CI runners have it.

## Questions for the human
- [x] **Q1 — Roles via bootstrap script.** Approved 2026-10-06. Create `abacus_owner`/`abacus_app` in `backend/migrations/bootstrap.sql` (run once per environment), not in a migration. **Recommendation:** yes.
- [x] **Q2 — Classification mechanism.** Approved 2026-10-06. ADR-031's `Field(json_schema_extra={"cls": ...})` behind a `classified()` helper, enforced by a unit test over every `abacus` model. **Recommendation:** yes.
- [x] **Q3 — Migration linter (ADR-015).** Approved 2026-10-06. Defer until the first destructive migration; track as a follow-up task. **Recommendation:** defer.
- [x] **Q4 — Protect `alembic.ini`, `migrations/env.py`, `migrations/bootstrap.sql`.** Approved 2026-10-06. They decide which role migrations run as, the timeouts, and the role privileges. **Recommendation:** yes.

## Handoff
- **Current state:** Implemented, both stage 4 reviews addressed, `make check` exit 0. PR open; awaiting the founder's line-by-line review (red).
- **Exact next step:** Confirm CI; founder reviews and merges; delete `work/approvals/TASK-005.yaml`; mark done; then TASK-006 plan (unit of work must own its transaction — see TASK-006 Gotchas).
- **Uncommitted or partial work:** none.
- **Known failing checks:** none.
- **Open issues:** branch protection off.
