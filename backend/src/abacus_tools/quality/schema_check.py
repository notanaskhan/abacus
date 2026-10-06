"""Tenant and row-level security schema check (ADR-014, ADR-015, ADR-080). PROTECTED.

Run: python -m abacus_tools.quality.schema_check

Starts Postgres from the compose image, applies bootstrap.sql, migrates to head, down to base and
up again (every migration must be reversible), then inspects the catalog. It fails on:
  - a table without `tenant_id uuid NOT NULL`, without row-level security enabled AND forced, or
    without the `tenant_isolation` policy on `app.tenant_id` (unless listed in NON_TENANT_TABLES)
  - any app privilege on a non-tenant table
  - a table not owned by abacus_owner
  - UPDATE or DELETE granted to abacus_app on an insert-only table (INSERT_ONLY_TABLES)
  - abacus_app with SUPERUSER, BYPASSRLS, CREATEROLE or CREATEDB, or owning any relation
  - a global table (GLOBAL_TABLES) with any app privilege
  - a table missing from TABLE_OWNERS, or listed there but absent (ADR-103)
  - an IMMUTABLE_TABLES table without enabled BEFORE UPDATE/DELETE/TRUNCATE triggers (ADR-004)
  - abacus_relay or abacus_identity (they bypass RLS) holding any privilege not in
    BYPASS_ROLE_GRANTS, or any other non-superuser role with BYPASSRLS

`provisioned_database()` is shared with the integration test fixtures, so tests and this gate build
the database the same way.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import asyncpg
import yaml
from alembic import command
from alembic.config import Config
from testcontainers.community.postgres import PostgresContainer

from abacus.kernel.db.migration import tenant_table

BACKEND = Path(__file__).resolve().parents[3]
REPO = BACKEND.parent
OWNER = "abacus_owner"
APP = "abacus_app"
# Tables without tenant_id: only infrastructure. Each entry is founder-reviewed (protected file).
NON_TENANT_TABLES = frozenset({"alembic_version"})
# Tables the app may insert into and read, never update or delete (ADR-004); TASK-009/010 add.
INSERT_ONLY_TABLES: frozenset[str] = frozenset(
    {"audit_events", "outbox", "evidence_versions", "ledger_snapshots", "trial_balance_lines"}
    | {"fulfilments"}
)
# Columns the app may supply on insert; everything else is server-set (TASK-006, TASK-008).
APP_INSERT_COLUMNS: dict[str, frozenset[str]] = {
    "audit_events": frozenset(
        {"tenant_id", "actor_kind", "actor_id", "action", "target_type", "target_id"}
        | {"before_ref", "after_ref", "trace_id"}
    ),
    "outbox": frozenset({"id", "tenant_id", "event_type", "payload"}),
    "clients": frozenset({"id", "tenant_id", "name"}),
    "client_entities": frozenset({"id", "tenant_id", "client_id", "name"}),
    "engagements": frozenset(
        {"id", "tenant_id", "client_id", "client_entity_id", "name", "created_by"}
        | {"fiscal_period_start", "fiscal_period_end"}
    ),
    "request_lists": frozenset({"id", "tenant_id", "engagement_id"}),
    "request_items": frozenset(
        {"id", "tenant_id", "engagement_id", "request_list_id", "description", "audit_area"}
        | {"created_by"}
    ),
    "engagement_members": frozenset({"tenant_id", "engagement_id", "user_id", "role"}),
    "evidence_items": frozenset(
        {"id", "tenant_id", "engagement_id", "title", "created_by_kind", "created_by_id"}
    ),
    "evidence_versions": frozenset(
        {"id", "tenant_id", "engagement_id", "evidence_item_id", "version_no", "fingerprint"}
        | {"storage_key", "storage_version_id", "size_bytes", "media_type", "source", "method"}
        | {"pulled_at", "period_start", "period_end", "client_entity_id", "snapshot_id"}
        | {"idempotency_key"}
    ),
}
APP_INSERT_COLUMNS.update(
    {
        "sync_runs": frozenset(
            {"id", "tenant_id", "connection_id", "engagement_id", "request_item_id", "dataset"}
            | {"period_start", "period_end", "started_by", "client_entity_id"}
        ),
        "ledger_snapshots": frozenset(
            {"id", "tenant_id", "client_entity_id", "period_start", "period_end", "pulled_at"}
            | {"source", "raw_fingerprint", "line_count", "total_debit", "total_credit"}
        ),
        "trial_balance_lines": frozenset(
            {"id", "tenant_id", "snapshot_id", "account_code", "account_name", "debit"}
            | {"credit", "source_ref"}
        ),
        "fulfilments": frozenset(
            {"id", "tenant_id", "request_item_id", "evidence_version_id", "created_by_kind"}
            | {"created_by_id", "engagement_id"}
        ),
        "connections": frozenset(),
    }
)
# Tables whose rows no role may change or remove: a BEFORE UPDATE OR DELETE trigger and a BEFORE
# TRUNCATE trigger must call this function (ADR-004 second layer, TASK-009).
IMMUTABLE_TABLES: dict[str, str] = {
    "evidence_versions": "evidence_versions_immutable",
    "ledger_snapshots": "ledger_immutable",
    "trial_balance_lines": "ledger_immutable",
}
# Columns the app may update; any other UPDATE on these tables is reported (TASK-008). Tables not
# listed here keep whatever their migration grants (insert-only tables grant none).
APP_UPDATE_COLUMNS: dict[str, frozenset[str]] = {
    "engagements": frozenset({"status"}),
    "request_items": frozenset({"status"}),
    "connections": frozenset({"status"}),
    "sync_runs": frozenset(
        {"status", "raw_storage_key", "raw_version_id", "raw_fingerprint", "snapshot_id"}
        | {"raw_size_bytes", "raw_pulled_at", "failure_code", "finished_at", "source"}
        | {"evidence_version_id"}
    ),
}
# Who owns each table (ADR-103): a module or kernel package. Every table must be listed, and every
# listed table must exist. Modules touch only their own tables (ADR-008).
TABLE_OWNERS: dict[str, str] = {
    "alembic_version": "migrations",
    "audit_events": "kernel.uow",
    "outbox": "kernel.uow",
    "firms": "identity",
    "users": "identity",
    "memberships": "identity",
    "engagement_members": "identity",
    "clients": "organisations",
    "client_entities": "organisations",
    "engagements": "engagements",
    "request_lists": "requests",
    "request_items": "requests",
    "evidence_items": "evidence",
    "evidence_versions": "evidence",
    "connections": "connections",
    "sync_runs": "connections",
    "ledger_snapshots": "ledger",
    "trial_balance_lines": "ledger",
    "fulfilments": "requests",
}
# Tables shared by every tenant, readable only through abacus_identity (ADR-002, TASK-007): the app
# role has no privileges on them at all. Each entry is founder-reviewed (protected file).
GLOBAL_TABLES = frozenset({"users"})
RELAY = "abacus_relay"
IDENTITY = "abacus_identity"
_LOCAL_PASSWORDS = {
    OWNER: "abacusowner",
    APP: "abacusapp",
    RELAY: "abacusrelay",
    IDENTITY: "abacusidentity",
}


@dataclass(frozen=True)
class Database:
    owner_url: str
    app_url: str
    relay_url: str
    identity_url: str
    superuser_dsn: str


def compose_image(service: str) -> str:
    loaded = cast(dict[str, object], yaml.safe_load((REPO / "docker-compose.yml").read_text()))
    services = cast(dict[str, dict[str, object]], loaded["services"])
    return str(services[service]["image"])


def _dsn(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)


async def _run_sql(dsn: str, *scripts: Path) -> None:
    conn = await asyncpg.connect(dsn)
    try:
        for script in scripts:
            await conn.execute(script.read_text())
    finally:
        await conn.close()


def migrate(owner_url: str, revision: str, *, down: bool = False) -> None:
    config = Config(str(BACKEND / "alembic.ini"))
    config.cmd_opts = argparse.Namespace(x=[f"url={owner_url}"])
    if down:
        command.downgrade(config, revision)
    else:
        command.upgrade(config, revision)


@contextmanager
def provisioned_database(*, roundtrip: bool = True) -> Generator[Database]:
    """Fresh Postgres from the compose image, bootstrapped and migrated to head."""
    with PostgresContainer(
        compose_image("db"), username="postgres", password="postgres", dbname="abacus", driver=None
    ) as container:
        host, port = container.get_container_host_ip(), container.get_exposed_port(5432)
        superuser = container.get_connection_url()
        migrations = BACKEND / "migrations"
        asyncio.run(
            _run_sql(superuser, migrations / "bootstrap.sql", migrations / "bootstrap-local.sql")
        )

        def url(role: str) -> str:
            return f"postgresql+asyncpg://{role}:{_LOCAL_PASSWORDS[role]}@{host}:{port}/abacus"

        migrate(url(OWNER), "head")
        if roundtrip:
            migrate(url(OWNER), "base", down=True)
            migrate(url(OWNER), "head")
        yield Database(url(OWNER), url(APP), url(RELAY), url(IDENTITY), superuser)


_TABLES = """
SELECT c.relname, pg_get_userbyid(c.relowner) AS owner, c.relrowsecurity, c.relforcerowsecurity
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p') ORDER BY c.relname
"""
_TENANT_COLUMN = """
SELECT format_type(a.atttypid, a.atttypmod) AS type, a.attnotnull
FROM pg_attribute a JOIN pg_class c ON c.oid = a.attrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relname = $1 AND a.attname = 'tenant_id' AND NOT a.attisdropped
"""
_POLICIES = """
SELECT policyname, permissive, roles::text[] AS roles, cmd, qual, with_check FROM pg_policies
WHERE schemaname = 'public' AND tablename = $1 ORDER BY policyname
"""
# Relations row-level security can't protect: views run as their owner unless security_invoker;
# materialized views and foreign tables never apply it.
_OTHER_RELATIONS = """
SELECT c.relname, c.relkind, pg_get_userbyid(c.relowner) AS owner, c.reloptions
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind IN ('v', 'm', 'f') ORDER BY c.relname
"""
_KINDS = {"v": "view", "m": "materialized view", "f": "foreign table"}
_LARGE_OBJECT_FUNCTIONS = r"""
SELECT p.oid::regprocedure::text AS name FROM pg_proc p
WHERE p.pronamespace = 'pg_catalog'::regnamespace
  AND (p.proname LIKE 'lo\_%' OR p.proname IN ('loread', 'lowrite'))
  AND has_function_privilege($1, p.oid, 'EXECUTE')
ORDER BY 1
"""
_PROBE = "abacus_policy_probe"


class _Recorder:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def execute(self, sqltext: str) -> object:
        self.statements.append(sqltext)
        return None


async def _canonical_policy(conn: asyncpg.Connection) -> tuple[str, str]:
    """`qual` and `with_check` as Postgres stores them for the canonical tenant_table policy."""
    recorder = _Recorder()
    tenant_table(recorder, _PROBE)
    # A temporary table: private to this connection and dropped afterwards, never in `public`.
    await conn.execute("CREATE TEMPORARY TABLE abacus_policy_probe (tenant_id uuid NOT NULL)")
    try:
        for statement in recorder.statements:
            await conn.execute(statement)
        row = await conn.fetchrow(
            "SELECT qual, with_check FROM pg_policies WHERE tablename = $1", _PROBE
        )
    finally:
        await conn.execute("DROP TABLE IF EXISTS pg_temp.abacus_policy_probe")
    if row is None:
        raise RuntimeError("could not derive the canonical tenant_isolation policy")
    return str(row["qual"]), str(row["with_check"])


def _policy_problems(
    name: str, policies: list[asyncpg.Record], canonical: tuple[str, str]
) -> list[str]:
    if not policies:
        return [f"{name}: missing tenant_isolation policy on app.tenant_id"]
    problems: list[str] = []
    if len(policies) > 1:
        problems.append(
            f"{name}: has {len(policies)} policies; exactly one (tenant_isolation) is allowed"
        )
    for policy in policies:
        exact = (
            policy["policyname"] == "tenant_isolation"
            and policy["permissive"] == "PERMISSIVE"
            and policy["cmd"] == "ALL"
            and list(policy["roles"]) == ["public"]
            and (str(policy["qual"]), str(policy["with_check"])) == canonical
        )
        if not exact:
            problems.append(
                f"{name}: policy {policy['policyname']} "
                "is not the canonical tenant_isolation policy"
            )
    return problems


_ROLE = (
    "SELECT rolsuper, rolbypassrls, rolcreaterole, rolcreatedb FROM pg_roles WHERE rolname = $1"
)
_ROLE_ATTRIBUTES = {
    "rolsuper": "SUPERUSER",
    "rolbypassrls": "BYPASSRLS",
    "rolcreaterole": "CREATEROLE",
    "rolcreatedb": "CREATEDB",
}
# The app role must own nothing: an owner can alter or drop the object and bypass its controls.
_OWNED = """
SELECT 'relation' AS kind, c.relname AS name FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE pg_get_userbyid(c.relowner) = $1 AND n.nspname NOT IN ('pg_catalog', 'information_schema')
"""
_OWNED_FUNCTIONS = """
SELECT 'function' AS kind, p.proname AS name FROM pg_proc p
WHERE pg_get_userbyid(p.proowner) = $1
"""
_OWNED_TYPES = """
SELECT 'type' AS kind, t.typname AS name FROM pg_type t
WHERE pg_get_userbyid(t.typowner) = $1 AND t.typrelid = 0 AND t.typelem = 0
"""
_OWNED_SCHEMAS = """
SELECT 'schema' AS kind, n.nspname AS name FROM pg_namespace n
WHERE pg_get_userbyid(n.nspowner) = $1
"""


RELAY_TABLE = "outbox"
RELAY_UPDATABLE = frozenset({"published_at", "attempts", "last_error", "next_attempt_at"})
ALL_COLUMNS = None  # in a Grant: every column of the table


@dataclass(frozen=True)
class Grant:
    """What a BYPASSRLS role may do to one table, column by column."""

    select: frozenset[str] | None = frozenset()
    update: frozenset[str] = frozenset()


# Bypass roles that never write: read-only by default (a second line behind the grants).
READ_ONLY_ROLES = frozenset({IDENTITY})
_ROLE_CONFIG = "SELECT rolconfig FROM pg_roles WHERE rolname = $1"
# Superusers bypass everything anyway; they're the operator's, not the application's.
_BYPASS_ROLES = "SELECT rolname FROM pg_roles WHERE rolbypassrls AND NOT rolsuper ORDER BY rolname"
# Roles that bypass row-level security, and everything each may touch (TASK-006, TASK-007).
BYPASS_ROLE_GRANTS: dict[str, dict[str, Grant]] = {
    RELAY: {RELAY_TABLE: Grant(select=ALL_COLUMNS, update=RELAY_UPDATABLE)},
    IDENTITY: {
        "users": Grant(select=ALL_COLUMNS),
        "memberships": Grant(
            select=frozenset({"tenant_id", "id", "user_id", "firm_role", "status"})
        ),
        "firms": Grant(select=frozenset({"tenant_id", "name"})),
    },
}
_TABLE_PRIVILEGES = ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER")
_COLUMNS = """
SELECT a.attname FROM pg_attribute a JOIN pg_class c ON c.oid = a.attrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relname = $1 AND a.attnum > 0 AND NOT a.attisdropped
ORDER BY a.attnum
"""
_SEQUENCES = """
SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind = 'S' ORDER BY c.relname
"""
_MEMBERSHIPS = """
SELECT r.rolname AS role FROM pg_auth_members m
JOIN pg_roles r ON r.oid = m.roleid JOIN pg_roles u ON u.oid = m.member
WHERE u.rolname = $1 ORDER BY r.rolname
"""
_ALL_RELATIONS = """
SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p', 'v', 'm', 'f') ORDER BY c.relname
"""


def _column_allowed(allowed: frozenset[str] | None, column: str) -> bool:
    return allowed is None or column in allowed


async def _bypass_role_problems(
    conn: asyncpg.Connection, role_name: str, grants: dict[str, Grant]
) -> list[str]:
    """A role that bypasses RLS sees every tenant: its privileges must stop at its grant list."""
    problems: list[str] = []
    role = await conn.fetchrow(_ROLE, role_name)
    if role is None:
        return [f"{role_name}: role missing"]
    for column, attribute in _ROLE_ATTRIBUTES.items():
        if column != "rolbypassrls" and role[column]:
            problems.append(f"{role_name}: has {attribute}")
    for query in (_OWNED, _OWNED_FUNCTIONS, _OWNED_TYPES, _OWNED_SCHEMAS):
        for owned in await conn.fetch(query, role_name):
            problems.append(f"{role_name}: owns {owned['kind']} {owned['name']}")
    for relation in await conn.fetch(_ALL_RELATIONS):
        name = str(relation["relname"])
        grant = grants.get(name)
        table_wide: set[str] = (
            {"SELECT"} if grant is not None and grant.select is ALL_COLUMNS else set()
        )
        for privilege in _TABLE_PRIVILEGES:
            if privilege not in table_wide and await conn.fetchval(
                "SELECT has_table_privilege($1, $2, $3)", role_name, f"public.{name}", privilege
            ):
                problems.append(f"{role_name}: has {privilege} on {name}")
        for column in await conn.fetch(_COLUMNS, name):
            col = str(column["attname"])
            permitted = {
                "SELECT": grant is not None and _column_allowed(grant.select, col),
                "UPDATE": grant is not None and col in grant.update,
                "INSERT": False,
                "REFERENCES": False,
            }
            for privilege, ok in permitted.items():
                if not ok and await conn.fetchval(
                    "SELECT has_column_privilege($1, $2, $3, $4)",
                    role_name,
                    f"public.{name}",
                    col,
                    privilege,
                ):
                    problems.append(f"{role_name}: may {privilege} {name}.{col}")
    for sequence in await conn.fetch(_SEQUENCES):
        name = str(sequence["relname"])
        for privilege in ("USAGE", "SELECT", "UPDATE"):
            if await conn.fetchval(
                "SELECT has_sequence_privilege($1, $2, $3)", role_name, f"public.{name}", privilege
            ):
                problems.append(f"{role_name}: has {privilege} on sequence {name}")
    for membership in await conn.fetch(_MEMBERSHIPS, role_name):
        problems.append(f"{role_name}: is a member of {membership['role']}")
    for function in await conn.fetch(_LARGE_OBJECT_FUNCTIONS, role_name):
        problems.append(f"{role_name}: can execute {function['name']}")
    if role_name in READ_ONLY_ROLES:
        config = cast(list[str] | None, await conn.fetchval(_ROLE_CONFIG, role_name)) or []
        if "default_transaction_read_only=on" not in config:
            problems.append(f"{role_name}: default_transaction_read_only is not on")
    return problems


async def _column_problems(
    conn: asyncpg.Connection, table: str, privilege: str, allowed: frozenset[str] | None
) -> list[str]:
    """Columns `privilege` is granted on beyond the declared list (none declared: not checked)."""
    if allowed is None:
        return []
    problems: list[str] = []
    for column in await conn.fetch(_COLUMNS, table):
        name = str(column["attname"])
        if name not in allowed and await conn.fetchval(
            "SELECT has_column_privilege($1, $2, $3, $4)", APP, f"public.{table}", name, privilege
        ):
            problems.append(f"{table}: {APP} may {privilege} {table}.{name}")
    return problems


async def _insert_column_problems(conn: asyncpg.Connection, table: str) -> list[str]:
    return await _column_problems(conn, table, "INSERT", APP_INSERT_COLUMNS.get(table))


_TRIGGERS = """
SELECT t.tgname, p.proname, p.prosrc, t.tgtype, t.tgenabled FROM pg_trigger t
JOIN pg_class c ON c.oid = t.tgrelid JOIN pg_namespace n ON n.oid = c.relnamespace
JOIN pg_proc p ON p.oid = t.tgfoid
WHERE n.nspname = 'public' AND c.relname = $1 AND NOT t.tgisinternal
"""
# pg_trigger.tgtype bits: 1 row-level, 2 before, 4 insert, 8 delete, 16 update, 32 truncate.
_ROW, _BEFORE, _DELETE, _UPDATE, _TRUNCATE = 1, 2, 8, 16, 32


async def _immutability_problems(conn: asyncpg.Connection, table: str, function: str) -> list[str]:
    covered = 0
    for trigger in await conn.fetch(_TRIGGERS, table):
        enabled = trigger["tgenabled"]
        state = enabled.decode() if isinstance(enabled, bytes) else str(enabled)
        # Only O (origin) and A (always) fire in normal sessions; D is disabled, R replica-only.
        if str(trigger["proname"]) != function or state not in ("O", "A"):
            continue
        body = str(trigger["prosrc"]).upper()
        if "RAISE EXCEPTION" not in body or "RETURN" in body:
            continue  # a function that no longer refuses doesn't count
        kind = int(trigger["tgtype"])
        if kind & _BEFORE:
            covered |= kind & (_DELETE | _UPDATE | _TRUNCATE)
    missing = [
        name
        for name, bit in (("UPDATE", _UPDATE), ("DELETE", _DELETE), ("TRUNCATE", _TRUNCATE))
        if not covered & bit
    ]
    return [
        f"{table}: no enabled BEFORE {op} trigger calling {function} that raises" for op in missing
    ]


async def _inspect(owner_dsn: str) -> list[str]:
    conn = await asyncpg.connect(owner_dsn)
    problems: list[str] = []
    try:
        canonical = await _canonical_policy(conn)
        tables = list(await conn.fetch(_TABLES))
        present = {str(table["relname"]) for table in tables}
        problems += [
            f"{name}: no owner in TABLE_OWNERS" for name in sorted(present - TABLE_OWNERS.keys())
        ]
        problems += [
            f"{name}: in TABLE_OWNERS but missing"
            for name in sorted(TABLE_OWNERS.keys() - present)
        ]
        for table in tables:
            name = str(table["relname"])
            if str(table["owner"]) != OWNER:
                problems.append(f"{name}: owned by {table['owner']}, not {OWNER}")
            if name in NON_TENANT_TABLES or name in GLOBAL_TABLES:
                for privilege in _TABLE_PRIVILEGES:
                    if await conn.fetchval(
                        "SELECT has_table_privilege($1, $2, $3)", APP, f"public.{name}", privilege
                    ):
                        problems.append(f"{name}: {APP} has {privilege} on a non-tenant table")
                for column in await conn.fetch(_COLUMNS, name):
                    col = str(column["attname"])
                    for privilege in ("SELECT", "INSERT", "UPDATE", "REFERENCES"):
                        if await conn.fetchval(
                            "SELECT has_column_privilege($1, $2, $3, $4)",
                            APP,
                            f"public.{name}",
                            col,
                            privilege,
                        ):
                            problems.append(f"{name}: {APP} may {privilege} {name}.{col}")
                continue
            column = await conn.fetchrow(_TENANT_COLUMN, name)
            if column is None or column["type"] != "uuid" or not column["attnotnull"]:
                problems.append(f"{name}: missing tenant_id uuid NOT NULL")
            if not table["relrowsecurity"]:
                problems.append(f"{name}: row-level security not enabled")
            if not table["relforcerowsecurity"]:
                problems.append(f"{name}: row-level security not forced")
            problems += _policy_problems(name, list(await conn.fetch(_POLICIES, name)), canonical)
            for privilege in ("TRUNCATE", "TRIGGER"):  # row-level security doesn't cover TRUNCATE
                if await conn.fetchval(
                    "SELECT has_table_privilege($1, $2, $3)", APP, f"public.{name}", privilege
                ):
                    problems.append(f"{name}: {APP} has {privilege}")
            problems += await _insert_column_problems(conn, name)
            problems += await _column_problems(conn, name, "UPDATE", APP_UPDATE_COLUMNS.get(name))
            if name in IMMUTABLE_TABLES:
                problems += await _immutability_problems(conn, name, IMMUTABLE_TABLES[name])
            if name in INSERT_ONLY_TABLES:
                for privilege in ("UPDATE", "DELETE"):
                    if await conn.fetchval(
                        "SELECT has_table_privilege($1, $2, $3)", APP, f"public.{name}", privilege
                    ):
                        problems.append(f"{name}: {APP} may {privilege} an insert-only table")
        for relation in await conn.fetch(_OTHER_RELATIONS):
            relkind = relation["relkind"]  # Postgres "char": asyncpg returns it as bytes
            code = relkind.decode() if isinstance(relkind, bytes) else str(relkind)
            name, kind = str(relation["relname"]), _KINDS[code]
            if str(relation["owner"]) != OWNER:
                problems.append(f"{name}: owned by {relation['owner']}, not {OWNER}")
            if kind == "view":
                raw = cast(list[object] | None, relation["reloptions"]) or []
                options = [str(o).lower() for o in raw]
                if not any(o in options for o in ("security_invoker=true", "security_invoker=on")):
                    problems.append(f"{name}: view is not security_invoker")
            elif await conn.fetchval(
                "SELECT has_table_privilege($1, $2, 'SELECT')", APP, f"public.{name}"
            ):
                problems.append(
                    f"{name}: {kind} is readable by {APP}; row-level security does not apply"
                )
        for function in await conn.fetch(_LARGE_OBJECT_FUNCTIONS, APP):
            problems.append(f"{APP}: can execute {function['name']}")
        for role in await conn.fetch(_BYPASS_ROLES):
            if str(role["rolname"]) not in BYPASS_ROLE_GRANTS:
                problems.append(f"{role['rolname']}: bypasses row-level security, not reviewed")
        for role_name, grants in BYPASS_ROLE_GRANTS.items():
            problems += await _bypass_role_problems(conn, role_name, grants)
        role = await conn.fetchrow(_ROLE, APP)
        if role is None:
            problems.append(f"{APP}: role missing")
        else:
            for column, attribute in _ROLE_ATTRIBUTES.items():
                if role[column]:
                    problems.append(f"{APP}: has {attribute}")
        for query in (_OWNED, _OWNED_FUNCTIONS, _OWNED_TYPES, _OWNED_SCHEMAS):
            for owned in await conn.fetch(query, APP):
                problems.append(f"{APP}: owns {owned['kind']} {owned['name']}")
    finally:
        await conn.close()
    return sorted(problems)


def check(dsn_owner: str, dsn_app: str) -> list[str]:
    """Problems in a migrated database, as `<table or role>: <problem>`, sorted."""
    del dsn_app  # the catalog is read as the owner; the app role is inspected by name
    return asyncio.run(_inspect(_dsn(dsn_owner)))


def main() -> int:
    with provisioned_database() as database:
        problems = check(database.owner_url, database.app_url)
    for problem in problems:
        print(problem)
    if problems:
        print(f"{len(problems)} schema problem(s).", file=sys.stderr)
        return 1
    print("schema_check: migrations reversible; every table tenant-scoped with forced RLS.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
