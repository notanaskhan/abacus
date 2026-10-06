"""AC-20: schema_check against real databases, one per violation in TASK-005 Design section 5.

Violations are built in a private container (the compose `db` image, `bootstrap.sql` applied,
role passwords reset to random values) so that role attributes can be altered without touching the
shared `migrated_db`, which is used only for the clean-database and `main()` cases. The tests are
synchronous because `check` and `main` run their own event loop.
"""

from __future__ import annotations

import asyncio
import secrets
from collections.abc import Iterator
from pathlib import Path
from typing import Protocol, cast

import asyncpg
import pytest
import yaml
from testcontainers.community.postgres import PostgresContainer

from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import provisioned_database

REPO = Path(__file__).resolve().parents[3]
DATABASE = "abacus"


class Migrated(Protocol):
    owner_url: str
    app_url: str


class Cluster:
    def __init__(self, admin: str, owner_url: str, app_url: str) -> None:
        self.admin = admin
        self.owner_url = owner_url
        self.app_url = app_url


def _plain(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://")


async def _execute(dsn: str, statements: list[str]) -> None:
    conn = await asyncpg.connect(_plain(dsn))
    try:
        for statement in statements:
            await conn.execute(statement)
    finally:
        await conn.close()


def _sql(dsn: str, *statements: str) -> None:
    asyncio.run(_execute(dsn, list(statements)))


async def _bootstrap(admin: str, passwords: dict[str, str]) -> None:
    conn = await asyncpg.connect(admin)
    try:
        await conn.execute((REPO / "backend" / "migrations" / "bootstrap.sql").read_text("utf-8"))
        for role, password in passwords.items():
            stmt = await conn.fetchval(
                "SELECT format('ALTER ROLE %I PASSWORD %L', $1::text, $2::text)", role, password
            )
            await conn.execute(stmt)
    finally:
        await conn.close()


@pytest.fixture(scope="module")
def cluster() -> Iterator[Cluster]:
    loaded = cast(dict[str, object], yaml.safe_load((REPO / "docker-compose.yml").read_text()))
    image = str(cast(dict[str, dict[str, object]], loaded["services"])["db"]["image"])
    superuser, superpass = "postgres", secrets.token_hex(8)
    with PostgresContainer(
        image, username=superuser, password=superpass, dbname=DATABASE, driver=None
    ) as container:
        host, port = container.get_container_host_ip(), container.get_exposed_port(5432)
        admin = f"postgresql://{superuser}:{superpass}@{host}:{port}/{DATABASE}"
        passwords = {"abacus_owner": secrets.token_hex(8), "abacus_app": secrets.token_hex(8)}
        asyncio.run(_bootstrap(admin, passwords))

        def url(role: str) -> str:
            return f"postgresql+asyncpg://{role}:{passwords[role]}@{host}:{port}/{DATABASE}"

        yield Cluster(admin, url("abacus_owner"), url("abacus_app"))


@pytest.fixture
def db(cluster: Cluster) -> Iterator[Cluster]:
    """The shared cluster, with every probe object and role change undone afterwards."""
    yield cluster
    _sql(
        cluster.admin,
        "DROP TABLE IF EXISTS probe, probe_a, probe_b, alembic_version CASCADE",
        "DROP SCHEMA IF EXISTS probe_schema CASCADE",
        "DROP VIEW IF EXISTS probe_view",
        "DROP MATERIALIZED VIEW IF EXISTS probe_mv",
        "REVOKE EXECUTE ON FUNCTION pg_catalog.lo_get(oid) FROM abacus_app",
        "ALTER ROLE abacus_app NOSUPERUSER NOBYPASSRLS NOCREATEROLE NOCREATEDB",
    )


COLUMNS = "id uuid PRIMARY KEY, tenant_id uuid NOT NULL, body text"
ENABLE = "ALTER TABLE {t} ENABLE ROW LEVEL SECURITY"
FORCE = "ALTER TABLE {t} FORCE ROW LEVEL SECURITY"
POLICY = (
    "CREATE POLICY tenant_isolation ON {t} "
    "USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) "
    "WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)"
)


def _good(t: str) -> list[str]:
    return [
        f"CREATE TABLE {t} ({COLUMNS})",
        ENABLE.format(t=t),
        FORCE.format(t=t),
        POLICY.format(t=t),
    ]


def _problems(db: Cluster, owner_statements: list[str], *admin_statements: str) -> list[str]:
    _sql(db.owner_url, *owner_statements)
    if admin_statements:
        _sql(db.admin, *admin_statements)
    return [m for m in sc.check(db.owner_url, db.app_url) if not _is_ownership_report(m)]


def _is_ownership_report(message: str) -> bool:
    """The probe databases below hold a few tables, not the migrated schema; their tests are about
    other checks, so the TABLE_OWNERS reports (tested at the end of this file) are set aside."""
    return message.endswith((": no owner in TABLE_OWNERS", ": in TABLE_OWNERS but missing"))


def _assert_reports(problems: list[str], subject: str, *keywords: str) -> None:
    assert problems, "expected a violation"
    assert problems == sorted(problems)
    assert any(m.startswith(f"{subject}: ") for m in problems), problems
    mine = " ".join(m.lower() for m in problems if m.startswith(f"{subject}: "))
    assert not keywords or any(k in mine for k in keywords), (keywords, problems)


# --- clean databases ---------------------------------------------------------------------------


def test_ac20_a_clean_migrated_database_passes(migrated_db: Migrated) -> None:
    assert sc.check(migrated_db.owner_url, migrated_db.app_url) == []


def test_ac20_a_database_with_a_correct_tenant_table_passes(db: Cluster) -> None:
    assert _problems(db, _good("probe")) == []


def test_ac20_alembic_version_is_allowlisted_for_tenant_rules(db: Cluster) -> None:
    problems = _problems(
        db,
        [
            "CREATE TABLE alembic_version (version_num varchar(32) PRIMARY KEY)",
            "REVOKE ALL ON alembic_version FROM abacus_app",
        ],
    )
    assert problems == []


def test_ac20_app_privilege_on_alembic_version_is_reported(db: Cluster) -> None:
    problems = _problems(
        db,
        [
            "CREATE TABLE alembic_version (version_num varchar(32) PRIMARY KEY)",
            "REVOKE ALL ON alembic_version FROM abacus_app",
            "GRANT SELECT ON alembic_version TO abacus_app",
        ],
    )
    _assert_reports(problems, "alembic_version", "select", "non-tenant")


# --- table violations --------------------------------------------------------------------------


def test_ac20_table_without_tenant_id_is_reported(db: Cluster) -> None:
    problems = _problems(
        db,
        [
            "CREATE TABLE probe (id uuid PRIMARY KEY, body text)",
            ENABLE.format(t="probe"),
            FORCE.format(t="probe"),
            "CREATE POLICY tenant_isolation ON probe "
            "USING (current_setting('app.tenant_id', true) IS NOT NULL)",
        ],
    )
    _assert_reports(problems, "probe", "tenant_id")


def test_ac20_nullable_tenant_id_is_reported(db: Cluster) -> None:
    problems = _problems(
        db,
        [
            "CREATE TABLE probe (id uuid PRIMARY KEY, tenant_id uuid, body text)",
            ENABLE.format(t="probe"),
            FORCE.format(t="probe"),
            POLICY.format(t="probe"),
        ],
    )
    _assert_reports(problems, "probe", "tenant_id", "null")


def test_ac20_tenant_id_of_the_wrong_type_is_reported(db: Cluster) -> None:
    problems = _problems(
        db,
        [
            "CREATE TABLE probe (id uuid PRIMARY KEY, tenant_id text NOT NULL, body text)",
            ENABLE.format(t="probe"),
            FORCE.format(t="probe"),
            "CREATE POLICY tenant_isolation ON probe "
            "USING (tenant_id = current_setting('app.tenant_id', true))",
        ],
    )
    _assert_reports(problems, "probe", "tenant_id", "uuid", "type")


def test_ac20_table_without_row_level_security_is_reported(db: Cluster) -> None:
    problems = _problems(db, [f"CREATE TABLE probe ({COLUMNS})", POLICY.format(t="probe")])
    _assert_reports(problems, "probe", "row", "rls", "security")


def test_ac20_table_with_rls_enabled_but_not_forced_is_reported(db: Cluster) -> None:
    problems = _problems(
        db,
        [f"CREATE TABLE probe ({COLUMNS})", ENABLE.format(t="probe"), POLICY.format(t="probe")],
    )
    _assert_reports(problems, "probe", "force")


def test_ac20_table_without_a_policy_is_reported(db: Cluster) -> None:
    problems = _problems(
        db,
        [f"CREATE TABLE probe ({COLUMNS})", ENABLE.format(t="probe"), FORCE.format(t="probe")],
    )
    _assert_reports(problems, "probe", "policy")


def test_ac20_policy_with_the_wrong_name_is_reported(db: Cluster) -> None:
    problems = _problems(
        db,
        [
            f"CREATE TABLE probe ({COLUMNS})",
            ENABLE.format(t="probe"),
            FORCE.format(t="probe"),
            "CREATE POLICY other_name ON probe "
            "USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)",
        ],
    )
    _assert_reports(problems, "probe", "policy", "tenant_isolation")


def test_ac20_policy_that_ignores_app_tenant_id_is_reported(db: Cluster) -> None:
    problems = _problems(
        db,
        [
            f"CREATE TABLE probe ({COLUMNS})",
            ENABLE.format(t="probe"),
            FORCE.format(t="probe"),
            "CREATE POLICY tenant_isolation ON probe USING (true) WITH CHECK (true)",
        ],
    )
    _assert_reports(problems, "probe", "policy", "app.tenant_id")


def test_ac20_table_owned_by_someone_other_than_abacus_owner_is_reported(db: Cluster) -> None:
    problems = _problems(db, _good("probe"), "ALTER TABLE probe OWNER TO postgres")
    _assert_reports(problems, "probe", "owner")


def test_ac20_every_violating_table_is_reported_and_messages_are_sorted(db: Cluster) -> None:
    problems = _problems(
        db,
        [
            "CREATE TABLE probe_b (id uuid PRIMARY KEY, body text)",
            f"CREATE TABLE probe_a ({COLUMNS})",
        ],
    )
    _assert_reports(problems, "probe_a")
    _assert_reports(problems, "probe_b", "tenant_id")
    assert problems == sorted(problems)
    assert all(m.startswith(("probe_a: ", "probe_b: ")) for m in problems)


# --- insert-only tables ------------------------------------------------------------------------


def test_ac20_insert_only_table_with_update_or_delete_granted_is_reported(
    db: Cluster, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sc, "INSERT_ONLY_TABLES", frozenset({"probe"}))
    problems = _problems(db, _good("probe"))
    _assert_reports(problems, "probe", "update", "delete", "insert-only", "insert only")


def test_ac20_insert_only_table_with_update_and_delete_revoked_passes(
    db: Cluster, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sc, "INSERT_ONLY_TABLES", frozenset({"probe"}))
    assert _problems(db, [*_good("probe"), "REVOKE UPDATE, DELETE ON probe FROM abacus_app"]) == []


def test_ac20_update_granted_on_a_table_not_declared_insert_only_is_fine(db: Cluster) -> None:
    assert _problems(db, _good("probe")) == []


# --- policies, views, large objects, privileges (contract revision 1) ------------------------

CANONICAL = "tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid"
NOT_CANONICAL = "policy tenant_isolation is not the canonical tenant_isolation policy"


def _table_with_policy(policy: str) -> list[str]:
    return [
        f"CREATE TABLE probe ({COLUMNS})",
        ENABLE.format(t="probe"),
        FORCE.format(t="probe"),
        policy,
    ]


@pytest.mark.parametrize(
    "policy",
    [
        f"CREATE POLICY tenant_isolation ON probe USING ({CANONICAL} OR true) "
        f"WITH CHECK ({CANONICAL})",
        f"CREATE POLICY tenant_isolation ON probe USING ({CANONICAL}) "
        f"WITH CHECK ({CANONICAL} OR true)",
        f"CREATE POLICY tenant_isolation ON probe TO abacus_owner USING ({CANONICAL}) "
        f"WITH CHECK ({CANONICAL})",
        f"CREATE POLICY tenant_isolation ON probe AS RESTRICTIVE USING ({CANONICAL}) "
        f"WITH CHECK ({CANONICAL})",
        f"CREATE POLICY tenant_isolation ON probe FOR SELECT USING ({CANONICAL})",
    ],
    ids=["using-or-true", "check-or-true", "to-owner", "restrictive", "select-only"],
)
def test_ac20_a_non_canonical_tenant_isolation_policy_is_reported(
    db: Cluster, policy: str
) -> None:
    problems = _problems(db, _table_with_policy(policy))
    assert f"probe: {NOT_CANONICAL}" in problems, problems


def test_ac20_a_second_permissive_policy_is_reported(db: Cluster) -> None:
    problems = _problems(db, [*_good("probe"), "CREATE POLICY extra ON probe USING (true)"])
    assert "probe: has 2 policies; exactly one (tenant_isolation) is allowed" in problems


def test_ac20_a_non_security_invoker_view_is_reported(db: Cluster) -> None:
    problems = _problems(db, [*_good("probe"), "CREATE VIEW probe_view AS SELECT * FROM probe"])
    assert "probe_view: view is not security_invoker" in problems, problems


def test_ac20_a_security_invoker_view_passes(db: Cluster) -> None:
    statements = [
        *_good("probe"),
        "CREATE VIEW probe_view WITH (security_invoker = true) AS SELECT * FROM probe",
    ]
    assert _problems(db, statements) == []


def test_ac20_a_materialized_view_readable_by_the_app_is_reported(db: Cluster) -> None:
    problems = _problems(
        db,
        [
            *_good("probe"),
            "CREATE MATERIALIZED VIEW probe_mv AS SELECT * FROM probe",
            "GRANT SELECT ON probe_mv TO abacus_app",
        ],
    )
    expected = (
        "probe_mv: materialized view is readable by abacus_app; row-level security does not apply"
    )
    assert expected in problems, problems


def test_ac20_app_able_to_execute_a_large_object_function_is_reported(db: Cluster) -> None:
    problems = _problems(db, [], "GRANT EXECUTE ON FUNCTION pg_catalog.lo_get(oid) TO abacus_app")
    assert any(m.startswith("abacus_app: can execute lo_get") for m in problems), problems


@pytest.mark.parametrize("privilege", ["TRUNCATE", "TRIGGER"])
def test_ac20_truncate_or_trigger_on_a_tenant_table_is_reported(
    db: Cluster, privilege: str
) -> None:
    statements = {
        "TRUNCATE": "GRANT TRUNCATE ON probe TO abacus_app",
        "TRIGGER": "GRANT TRIGGER ON probe TO abacus_app",
    }
    problems = _problems(db, _good("probe"), statements[privilege])
    _assert_reports(problems, "probe", privilege.lower())


def test_ac20_bootstrap_run_twice_still_passes_the_check() -> None:
    with provisioned_database(roundtrip=False) as database:
        script = (REPO / "backend" / "migrations" / "bootstrap.sql").read_text("utf-8")
        _sql(database.superuser_dsn, script, script)
        assert sc.check(database.owner_url, database.app_url) == []


# --- roles -------------------------------------------------------------------------------------


@pytest.mark.parametrize("attribute", ["BYPASSRLS", "SUPERUSER"])
def test_ac20_app_role_with_bypassrls_or_superuser_is_reported(
    db: Cluster, attribute: str
) -> None:
    statements = {
        "BYPASSRLS": "ALTER ROLE abacus_app BYPASSRLS",
        "SUPERUSER": "ALTER ROLE abacus_app SUPERUSER",
    }
    problems = _problems(db, _good("probe"), statements[attribute])
    _assert_reports(problems, "abacus_app", attribute.lower())


def test_ac20_app_role_owning_a_table_is_reported(db: Cluster) -> None:
    problems = _problems(db, _good("probe"), "ALTER TABLE probe OWNER TO abacus_app")
    assert problems
    assert any("abacus_app" in m for m in problems), problems
    assert problems == sorted(problems)


def test_ac20_app_role_owning_a_non_table_object_is_reported(db: Cluster) -> None:
    problems = _problems(db, [], "CREATE SCHEMA probe_schema AUTHORIZATION abacus_app")
    assert any("abacus_app" in m for m in problems), problems


# --- main --------------------------------------------------------------------------------------


def test_ac20_main_provisions_its_own_database_and_exits_0_when_clean() -> None:
    assert sc.main() == 0


def test_ac20_main_exits_1_and_prints_every_problem(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fake_check(dsn_owner: str, dsn_app: str) -> list[str]:
        assert dsn_owner != dsn_app
        return ["probe: no policy", "probe_b: missing tenant_id"]

    monkeypatch.setattr(sc, "check", fake_check)
    assert sc.main() == 1
    output = capsys.readouterr()
    text = output.out + output.err
    assert "probe: no policy" in text
    assert "probe_b: missing tenant_id" in text


# --- relay role and the audit and outbox tables (TASK-006) -----------------------------------

OUTBOX_DDL = (
    "CREATE TABLE outbox (id uuid PRIMARY KEY, tenant_id uuid NOT NULL, "
    "seq bigint GENERATED ALWAYS AS IDENTITY, occurred_at timestamptz NOT NULL DEFAULT now(), "
    "event_type text, payload jsonb, published_at timestamptz, attempts int NOT NULL DEFAULT 0, "
    "last_error text, next_attempt_at timestamptz)"
)
AUDIT_DDL = (
    "CREATE TABLE audit_events (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), "
    "tenant_id uuid NOT NULL, seq bigint GENERATED ALWAYS AS IDENTITY, "
    "occurred_at timestamptz NOT NULL DEFAULT now(), actor_kind text, actor_id text, "
    "action text, target_type text, target_id text, before_ref jsonb, after_ref jsonb, "
    "trace_id text)"
)
AUDIT_INSERTABLE = (
    "tenant_id, actor_kind, actor_id, action, target_type, target_id, before_ref, after_ref, "
    "trace_id"
)
OUTBOX_INSERTABLE = "id, tenant_id, event_type, payload"
RELAY_OK = [
    "GRANT SELECT ON outbox TO abacus_relay",
    "GRANT UPDATE (published_at, attempts, last_error, next_attempt_at) ON outbox TO abacus_relay",
]


def _protect(table: str, insertable: str) -> list[str]:
    return [
        ENABLE.format(t=table),
        FORCE.format(t=table),
        POLICY.format(t=table),
        f"REVOKE UPDATE, DELETE, INSERT ON {table} FROM abacus_app",
        f"GRANT INSERT ({insertable}) ON {table} TO abacus_app",
    ]


def _relay_tables() -> list[str]:
    return [
        OUTBOX_DDL,
        *_protect("outbox", OUTBOX_INSERTABLE),
        AUDIT_DDL,
        *_protect("audit_events", AUDIT_INSERTABLE),
        *RELAY_OK,
    ]


@pytest.fixture
def relay_db(db: Cluster) -> Iterator[Cluster]:
    yield db
    _sql(
        db.admin,
        "DROP TABLE IF EXISTS outbox, audit_events CASCADE",
        "ALTER ROLE abacus_relay NOSUPERUSER NOCREATEROLE NOCREATEDB",
        "REVOKE pg_monitor FROM abacus_relay",
    )


def test_ac20_a_correct_relay_and_insert_only_audit_tables_pass(relay_db: Cluster) -> None:
    assert _problems(relay_db, _relay_tables()) == []


def test_ac20_relay_with_privileges_on_another_table_is_reported(relay_db: Cluster) -> None:
    problems = _problems(
        relay_db,
        [*_relay_tables(), *_good("probe")],
        "GRANT SELECT ON probe TO abacus_relay",
    )
    _assert_reports(problems, "abacus_relay", "probe", "select")


def test_ac20_relay_with_privileges_on_audit_events_is_reported(relay_db: Cluster) -> None:
    problems = _problems(relay_db, _relay_tables(), "GRANT SELECT ON audit_events TO abacus_relay")
    _assert_reports(problems, "abacus_relay", "audit_events", "select")


@pytest.mark.parametrize("column", ["payload", "event_type", "tenant_id"])
def test_ac20_relay_update_on_a_column_other_than_the_status_columns_is_reported(
    relay_db: Cluster, column: str
) -> None:
    statements = {
        "payload": "GRANT UPDATE (payload) ON outbox TO abacus_relay",
        "event_type": "GRANT UPDATE (event_type) ON outbox TO abacus_relay",
        "tenant_id": "GRANT UPDATE (tenant_id) ON outbox TO abacus_relay",
    }
    problems = _problems(relay_db, _relay_tables(), statements[column])
    _assert_reports(problems, "abacus_relay", "update", "outbox", column)


@pytest.mark.parametrize("privilege", ["UPDATE", "DELETE", "INSERT"])
def test_ac20_relay_with_a_table_wide_write_privilege_on_outbox_is_reported(
    relay_db: Cluster, privilege: str
) -> None:
    statements = {
        "UPDATE": "GRANT UPDATE ON outbox TO abacus_relay",
        "DELETE": "GRANT DELETE ON outbox TO abacus_relay",
        "INSERT": "GRANT INSERT ON outbox TO abacus_relay",
    }
    problems = _problems(relay_db, _relay_tables(), statements[privilege])
    _assert_reports(problems, "abacus_relay", privilege.lower(), "outbox")


@pytest.mark.parametrize("attribute", ["SUPERUSER", "CREATEROLE", "CREATEDB"])
def test_ac20_relay_role_with_a_dangerous_attribute_is_reported(
    relay_db: Cluster, attribute: str
) -> None:
    statements = {
        "SUPERUSER": "ALTER ROLE abacus_relay SUPERUSER",
        "CREATEROLE": "ALTER ROLE abacus_relay CREATEROLE",
        "CREATEDB": "ALTER ROLE abacus_relay CREATEDB",
    }
    problems = _problems(relay_db, _relay_tables(), statements[attribute])
    _assert_reports(problems, "abacus_relay", attribute.lower())


def test_ac20_relay_role_owning_a_table_is_reported(relay_db: Cluster) -> None:
    problems = _problems(relay_db, _good("probe"), "ALTER TABLE probe OWNER TO abacus_relay")
    assert any(m.startswith("abacus_relay: ") and "owns" in m for m in problems), problems


@pytest.mark.parametrize("table", ["audit_events", "outbox"])
@pytest.mark.parametrize("privilege", ["UPDATE", "DELETE"])
def test_ac20_app_update_or_delete_on_audit_events_or_outbox_is_reported(
    relay_db: Cluster, table: str, privilege: str
) -> None:
    grants = {
        ("audit_events", "UPDATE"): "GRANT UPDATE ON audit_events TO abacus_app",
        ("audit_events", "DELETE"): "GRANT DELETE ON audit_events TO abacus_app",
        ("outbox", "UPDATE"): "GRANT UPDATE ON outbox TO abacus_app",
        ("outbox", "DELETE"): "GRANT DELETE ON outbox TO abacus_app",
    }
    problems = _problems(relay_db, _relay_tables(), grants[(table, privilege)])
    assert f"{table}: abacus_app may {privilege} an insert-only table" in problems, problems


def test_ac20_relay_may_update_next_attempt_at(relay_db: Cluster) -> None:
    statements = [
        *_relay_tables()[:-2],
        "GRANT SELECT ON outbox TO abacus_relay",
        "GRANT UPDATE (next_attempt_at) ON outbox TO abacus_relay",
    ]
    assert _problems(relay_db, statements) == []


@pytest.mark.parametrize("column", ["seq", "id", "occurred_at"])
def test_ac20_app_insert_on_a_non_allowed_audit_events_column_is_reported(
    relay_db: Cluster, column: str
) -> None:
    grants = {
        "seq": "GRANT INSERT (seq) ON audit_events TO abacus_app",
        "id": "GRANT INSERT (id) ON audit_events TO abacus_app",
        "occurred_at": "GRANT INSERT (occurred_at) ON audit_events TO abacus_app",
    }
    problems = _problems(relay_db, _relay_tables(), grants[column])
    assert f"audit_events: abacus_app may INSERT audit_events.{column}" in problems, problems


@pytest.mark.parametrize("column", ["published_at", "attempts", "last_error", "next_attempt_at"])
def test_ac20_app_insert_on_a_non_allowed_outbox_column_is_reported(
    relay_db: Cluster, column: str
) -> None:
    grants = {
        "published_at": "GRANT INSERT (published_at) ON outbox TO abacus_app",
        "attempts": "GRANT INSERT (attempts) ON outbox TO abacus_app",
        "last_error": "GRANT INSERT (last_error) ON outbox TO abacus_app",
        "next_attempt_at": "GRANT INSERT (next_attempt_at) ON outbox TO abacus_app",
    }
    problems = _problems(relay_db, _relay_tables(), grants[column])
    assert f"outbox: abacus_app may INSERT outbox.{column}" in problems, problems


def test_ac20_app_with_table_wide_insert_on_outbox_is_reported(relay_db: Cluster) -> None:
    problems = _problems(relay_db, _relay_tables(), "GRANT INSERT ON outbox TO abacus_app")
    assert "outbox: abacus_app may INSERT outbox.published_at" in problems, problems


@pytest.mark.parametrize("privilege", ["USAGE", "SELECT", "UPDATE"])
def test_ac20_relay_with_a_privilege_on_a_sequence_is_reported(
    relay_db: Cluster, privilege: str
) -> None:
    grants = {
        "USAGE": "GRANT USAGE ON SEQUENCE outbox_seq_seq TO abacus_relay",
        "SELECT": "GRANT SELECT ON SEQUENCE outbox_seq_seq TO abacus_relay",
        "UPDATE": "GRANT UPDATE ON SEQUENCE outbox_seq_seq TO abacus_relay",
    }
    problems = _problems(relay_db, _relay_tables(), grants[privilege])
    expected = f"abacus_relay: has {privilege} on sequence outbox_seq_seq"
    assert expected in problems, problems


def test_ac20_relay_membership_in_another_role_is_reported(relay_db: Cluster) -> None:
    problems = _problems(relay_db, _relay_tables(), "GRANT pg_monitor TO abacus_relay")
    assert "abacus_relay: is a member of pg_monitor" in problems, problems


def test_ac20_relay_message_formats_for_table_privileges_and_columns(relay_db: Cluster) -> None:
    problems = _problems(
        relay_db,
        [*_relay_tables(), *_good("probe")],
        "GRANT SELECT ON probe TO abacus_relay",
        "GRANT UPDATE (payload) ON outbox TO abacus_relay",
    )
    assert "abacus_relay: has SELECT on probe" in problems, problems
    assert "abacus_relay: may UPDATE outbox.payload" in problems, problems


def test_ac20_a_declared_column_list_is_enforced_for_a_patched_insert_only_table(
    db: Cluster, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sc, "INSERT_ONLY_TABLES", frozenset({"probe"}))
    monkeypatch.setattr(sc, "APP_INSERT_COLUMNS", {"probe": frozenset({"id", "tenant_id"})})
    problems = _problems(
        db,
        [
            *_good("probe"),
            "REVOKE UPDATE, DELETE, INSERT ON probe FROM abacus_app",
            "GRANT INSERT (id, tenant_id, body) ON probe TO abacus_app",
        ],
    )
    assert problems == ["probe: abacus_app may INSERT probe.body"], problems


# --- identity role and the global users table (TASK-007) -----------------------------------------

USERS_DDL = (
    "CREATE TABLE users (id uuid PRIMARY KEY, idp_issuer text, idp_subject text, email text, "
    "display_name text, created_at timestamptz)"
)
MEMBERSHIPS_DDL = (
    "CREATE TABLE memberships (tenant_id uuid NOT NULL, id uuid, user_id uuid, firm_role text, "
    "status text, created_at timestamptz, revoked_at timestamptz)"
)
FIRMS_DDL = "CREATE TABLE firms (tenant_id uuid NOT NULL, name text, created_at timestamptz)"
MEMBERS_DDL = (
    "CREATE TABLE engagement_members (tenant_id uuid NOT NULL, engagement_id uuid, "
    "user_id uuid, role text)"
)
IDENTITY_OK = [
    USERS_DDL,
    "REVOKE ALL ON users FROM abacus_app",
    "GRANT SELECT ON users TO abacus_identity",
    MEMBERSHIPS_DDL,
    *[stmt.format(t="memberships") for stmt in (ENABLE, FORCE, POLICY)],
    "GRANT SELECT (tenant_id, id, user_id, firm_role, status) ON memberships TO abacus_identity",
    FIRMS_DDL,
    *[stmt.format(t="firms") for stmt in (ENABLE, FORCE, POLICY)],
    "GRANT SELECT (tenant_id, name) ON firms TO abacus_identity",
]


@pytest.fixture
def identity_db(db: Cluster) -> Iterator[Cluster]:
    yield db
    _sql(
        db.admin,
        "DROP TABLE IF EXISTS users, memberships, firms, engagement_members CASCADE",
        "DROP SEQUENCE IF EXISTS probe_seq",
        "ALTER ROLE abacus_identity NOSUPERUSER NOCREATEROLE NOCREATEDB",
        "ALTER ROLE abacus_identity SET default_transaction_read_only = on",
        "REVOKE EXECUTE ON FUNCTION pg_catalog.lo_get(oid) FROM abacus_identity, abacus_relay",
        "DO $$ BEGIN IF pg_has_role('abacus_identity', 'pg_monitor', 'MEMBER') THEN "
        "REVOKE pg_monitor FROM abacus_identity; END IF; END $$",
    )


def test_ac20_correct_identity_grants_and_a_global_users_table_pass(identity_db: Cluster) -> None:
    assert _problems(identity_db, IDENTITY_OK) == []


@pytest.mark.parametrize(
    "privilege", ["INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER"]
)
def test_ac20_identity_with_a_write_privilege_on_users_is_reported(
    identity_db: Cluster, privilege: str
) -> None:
    problems = _problems(
        identity_db, IDENTITY_OK, f"GRANT {privilege} ON users TO abacus_identity"
    )
    assert f"abacus_identity: has {privilege} on users" in problems, problems


@pytest.mark.parametrize("privilege", ["SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE"])
def test_ac20_identity_with_a_privilege_on_another_table_is_reported(
    identity_db: Cluster, privilege: str
) -> None:
    problems = _problems(
        identity_db, _good("probe"), f"GRANT {privilege} ON probe TO abacus_identity"
    )
    assert f"abacus_identity: has {privilege} on probe" in problems, problems


def test_ac20_identity_with_a_privilege_on_engagement_members_is_reported(
    identity_db: Cluster,
) -> None:
    statements = [
        MEMBERS_DDL,
        *[stmt.format(t="engagement_members") for stmt in (ENABLE, FORCE, POLICY)],
    ]
    problems = _problems(
        identity_db, statements, "GRANT SELECT ON engagement_members TO abacus_identity"
    )
    assert "abacus_identity: has SELECT on engagement_members" in problems, problems


@pytest.mark.parametrize("column", ["created_at", "revoked_at"])
def test_ac20_identity_select_on_an_extra_memberships_column_is_reported(
    identity_db: Cluster, column: str
) -> None:
    problems = _problems(
        identity_db, IDENTITY_OK, f"GRANT SELECT ({column}) ON memberships TO abacus_identity"
    )
    assert f"abacus_identity: may SELECT memberships.{column}" in problems, problems


def test_ac20_identity_table_wide_select_on_memberships_is_reported(identity_db: Cluster) -> None:
    problems = _problems(
        identity_db, IDENTITY_OK, "GRANT SELECT ON memberships TO abacus_identity"
    )
    assert "abacus_identity: has SELECT on memberships" in problems, problems
    assert "abacus_identity: may SELECT memberships.created_at" in problems, problems


def test_ac20_identity_select_on_firms_created_at_is_reported(identity_db: Cluster) -> None:
    problems = _problems(
        identity_db, IDENTITY_OK, "GRANT SELECT (created_at) ON firms TO abacus_identity"
    )
    assert "abacus_identity: may SELECT firms.created_at" in problems, problems


@pytest.mark.parametrize("table", ["memberships", "firms", "users"])
def test_ac20_identity_update_on_a_column_is_reported(identity_db: Cluster, table: str) -> None:
    column = {"memberships": "status", "firms": "name", "users": "email"}[table]
    problems = _problems(
        identity_db, IDENTITY_OK, f"GRANT UPDATE ({column}) ON {table} TO abacus_identity"
    )
    assert f"abacus_identity: may UPDATE {table}.{column}" in problems, problems


def test_ac20_identity_insert_on_a_column_is_reported(identity_db: Cluster) -> None:
    problems = _problems(
        identity_db, IDENTITY_OK, "GRANT INSERT (email) ON users TO abacus_identity"
    )
    assert "abacus_identity: may INSERT users.email" in problems, problems


@pytest.mark.parametrize("attribute", ["SUPERUSER", "CREATEROLE", "CREATEDB"])
def test_ac20_identity_role_with_a_dangerous_attribute_is_reported(
    identity_db: Cluster, attribute: str
) -> None:
    problems = _problems(identity_db, IDENTITY_OK, f"ALTER ROLE abacus_identity {attribute}")
    _assert_reports(problems, "abacus_identity", attribute.lower())


def test_ac20_identity_role_owning_a_table_is_reported(identity_db: Cluster) -> None:
    problems = _problems(identity_db, _good("probe"), "ALTER TABLE probe OWNER TO abacus_identity")
    assert any(m.startswith("abacus_identity: ") and "owns" in m for m in problems), problems


@pytest.mark.parametrize("privilege", ["USAGE", "SELECT", "UPDATE"])
def test_ac20_identity_with_a_privilege_on_a_sequence_is_reported(
    identity_db: Cluster, privilege: str
) -> None:
    problems = _problems(
        identity_db,
        ["CREATE SEQUENCE probe_seq"],
        f"GRANT {privilege} ON SEQUENCE probe_seq TO abacus_identity",
    )
    assert f"abacus_identity: has {privilege} on sequence probe_seq" in problems, problems


def test_ac20_identity_membership_in_another_role_is_reported(identity_db: Cluster) -> None:
    problems = _problems(identity_db, IDENTITY_OK, "GRANT pg_monitor TO abacus_identity")
    assert "abacus_identity: is a member of pg_monitor" in problems, problems


def test_ac20_identity_role_that_is_not_read_only_by_default_is_reported(
    identity_db: Cluster,
) -> None:
    problems = _problems(
        identity_db, IDENTITY_OK, "ALTER ROLE abacus_identity RESET default_transaction_read_only"
    )
    assert "abacus_identity: default_transaction_read_only is not on" in problems, problems


def test_ac20_identity_role_set_to_read_write_by_default_is_reported(identity_db: Cluster) -> None:
    problems = _problems(
        identity_db,
        IDENTITY_OK,
        "ALTER ROLE abacus_identity SET default_transaction_read_only = off",
    )
    assert "abacus_identity: default_transaction_read_only is not on" in problems, problems


@pytest.mark.parametrize("role", ["abacus_identity", "abacus_relay"])
def test_ac20_bypass_role_able_to_execute_a_large_object_function_is_reported(
    identity_db: Cluster, role: str
) -> None:
    problems = _problems(
        identity_db, IDENTITY_OK, f"GRANT EXECUTE ON FUNCTION pg_catalog.lo_get(oid) TO {role}"
    )
    assert any(m.startswith(f"{role}: can execute ") and "lo_get" in m for m in problems), problems


# --- the global users table: abacus_app has nothing on it ---------------------------------------


@pytest.mark.parametrize("privilege", ["SELECT", "INSERT", "UPDATE", "DELETE"])
def test_ac20_app_privilege_on_users_is_reported(identity_db: Cluster, privilege: str) -> None:
    problems = _problems(identity_db, [*IDENTITY_OK], f"GRANT {privilege} ON users TO abacus_app")
    assert f"users: abacus_app has {privilege} on a non-tenant table" in problems, problems


@pytest.mark.parametrize("privilege", ["SELECT", "INSERT", "UPDATE"])
def test_ac20_app_column_privilege_on_users_is_reported(
    identity_db: Cluster, privilege: str
) -> None:
    problems = _problems(
        identity_db, IDENTITY_OK, f"GRANT {privilege} (email) ON users TO abacus_app"
    )
    assert f"users: abacus_app may {privilege} users.email" in problems, problems


def test_ac20_a_users_table_left_with_the_default_app_grants_is_reported(
    identity_db: Cluster,
) -> None:
    problems = _problems(identity_db, [USERS_DDL, "GRANT SELECT ON users TO abacus_identity"])
    assert "users: abacus_app has SELECT on a non-tenant table" in problems, problems
    assert "users: abacus_app may SELECT users.id" in problems, problems
    assert problems == sorted(problems)


def test_ac20_a_global_users_table_is_not_held_to_the_tenant_table_rules(
    identity_db: Cluster,
) -> None:
    problems = _problems(identity_db, IDENTITY_OK)
    assert not [m for m in problems if m.startswith("users: ")], problems
    assert not [m for m in problems if "tenant_id" in m or "row-level" in m], problems


def test_ac20_a_table_named_like_a_tenant_table_still_needs_tenant_id(
    identity_db: Cluster,
) -> None:
    problems = _problems(
        identity_db,
        [
            "CREATE TABLE probe (id uuid PRIMARY KEY, body text)",
            ENABLE.format(t="probe"),
            FORCE.format(t="probe"),
            "CREATE POLICY tenant_isolation ON probe USING (true)",
        ],
    )
    _assert_reports(problems, "probe", "tenant_id")


@pytest.fixture
def probe_role(db: Cluster) -> Iterator[str]:
    yield "probe_bypass"
    _sql(db.admin, "DROP ROLE IF EXISTS probe_bypass")


def test_ac20_an_unreviewed_bypassrls_role_is_reported(db: Cluster, probe_role: str) -> None:
    problems = _problems(db, _good("probe"), f"CREATE ROLE {probe_role} LOGIN BYPASSRLS")
    assert f"{probe_role}: bypasses row-level security, not reviewed" in problems, problems
    assert problems == sorted(problems)


def test_ac20_a_role_without_bypassrls_is_not_reported_as_unreviewed(
    db: Cluster, probe_role: str
) -> None:
    problems = _problems(db, _good("probe"), f"CREATE ROLE {probe_role} LOGIN")
    assert not [m for m in problems if "not reviewed" in m], problems


def test_ac20_the_reviewed_bypass_roles_are_not_reported_as_unreviewed(db: Cluster) -> None:
    problems = _problems(db, _good("probe"))
    assert not [m for m in problems if "not reviewed" in m], problems


# --- TABLE_OWNERS (ADR-103) ----------------------------------------------------------------------


def _public_tables(dsn: str) -> set[str]:
    async def fetch() -> set[str]:
        conn = await asyncpg.connect(dsn)
        try:
            rows = await conn.fetch(
                "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')"
            )
        finally:
            await conn.close()
        return {str(row["relname"]) for row in rows}

    return asyncio.run(fetch())


def test_ac20_table_owners_lists_exactly_the_tables_of_the_migrated_schema(
    migrated_db: Migrated,
) -> None:
    tables = _public_tables(_plain(migrated_db.owner_url))
    assert set(sc.TABLE_OWNERS) == tables
    assert {
        "clients",
        "client_entities",
        "engagements",
        "request_lists",
        "request_items",
    } <= tables


@pytest.mark.parametrize(
    ("table", "owner"),
    [
        ("clients", "organisations"),
        ("client_entities", "organisations"),
        ("engagements", "engagements"),
        ("request_lists", "requests"),
        ("request_items", "requests"),
        ("engagement_members", "identity"),
        ("memberships", "identity"),
        ("connections", "connections"),
        ("sync_runs", "connections"),
        ("ledger_snapshots", "ledger"),
        ("trial_balance_lines", "ledger"),
        ("fulfilments", "requests"),
        ("agent_runs", "agents"),
        ("screening_results", "agents"),
        ("usage_records", "ai_gateway"),
    ],
)
def test_ac20_table_owners_assigns_the_new_tables_to_their_modules(table: str, owner: str) -> None:
    assert sc.TABLE_OWNERS[table] == owner


@pytest.mark.parametrize("table", ["request_items", "clients", "engagements"])
def test_ac20_a_table_missing_from_table_owners_is_reported(
    migrated_db: Migrated, monkeypatch: pytest.MonkeyPatch, table: str
) -> None:
    monkeypatch.setattr(
        sc, "TABLE_OWNERS", {k: v for k, v in sc.TABLE_OWNERS.items() if k != table}
    )
    assert sc.check(migrated_db.owner_url, migrated_db.app_url) == [
        f"{table}: no owner in TABLE_OWNERS"
    ]


def test_ac20_a_table_listed_in_table_owners_but_absent_is_reported(
    migrated_db: Migrated, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sc, "TABLE_OWNERS", {**sc.TABLE_OWNERS, "zz_ghost": "engagements"})
    assert sc.check(migrated_db.owner_url, migrated_db.app_url) == [
        "zz_ghost: in TABLE_OWNERS but missing"
    ]


def test_ac20_both_table_owners_reports_are_sorted_together_with_other_problems(
    migrated_db: Migrated, monkeypatch: pytest.MonkeyPatch
) -> None:
    owners = {k: v for k, v in sc.TABLE_OWNERS.items() if k != "outbox"}
    monkeypatch.setattr(sc, "TABLE_OWNERS", {**owners, "aa_ghost": "requests"})
    problems = sc.check(migrated_db.owner_url, migrated_db.app_url)
    assert problems == sorted(problems)
    assert set(problems) == {
        "aa_ghost: in TABLE_OWNERS but missing",
        "outbox: no owner in TABLE_OWNERS",
    }


def test_ac20_a_table_nobody_owns_in_a_database_without_the_migrations_is_reported(
    db: Cluster,
) -> None:
    sql_problems = sc.check(*_urls(db, _good("probe")))
    assert "probe: no owner in TABLE_OWNERS" in sql_problems
    assert "engagements: in TABLE_OWNERS but missing" in sql_problems


def _urls(db: Cluster, owner_statements: list[str]) -> tuple[str, str]:
    _sql(db.owner_url, *owner_statements)
    return db.owner_url, db.app_url


# --- column grants on tenant tables (contract revision 1) ----------------------------------------


def test_ac20_declared_insert_columns_apply_to_tables_that_are_not_insert_only(
    db: Cluster, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sc, "APP_INSERT_COLUMNS", {"probe": frozenset({"id", "tenant_id"})})
    problems = _problems(db, _good("probe"))  # the app holds INSERT on every column by default
    assert "probe: abacus_app may INSERT probe.body" in problems


def test_ac20_declared_insert_columns_that_match_the_grant_pass(
    db: Cluster, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        sc, "APP_INSERT_COLUMNS", {"probe": frozenset({"id", "tenant_id", "body"})}
    )
    assert _problems(db, _good("probe")) == []


def test_ac20_an_extra_update_column_is_reported(
    db: Cluster, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sc, "APP_UPDATE_COLUMNS", {"probe": frozenset({"body"})})
    problems = _problems(db, _good("probe"))
    assert "probe: abacus_app may UPDATE probe.id" in problems
    assert "probe: abacus_app may UPDATE probe.tenant_id" in problems
    assert not any(m == "probe: abacus_app may UPDATE probe.body" for m in problems)
    assert problems == sorted(problems)


def test_ac20_update_limited_to_the_declared_column_passes(
    db: Cluster, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sc, "APP_UPDATE_COLUMNS", {"probe": frozenset({"body"})})
    problems = _problems(
        db,
        _good("probe"),
        "REVOKE UPDATE ON probe FROM abacus_app",
        "GRANT UPDATE (body) ON probe TO abacus_app",
    )
    assert not [m for m in problems if "may UPDATE" in m]


def test_ac20_the_real_update_column_declarations_match_the_contract() -> None:
    assert {
        "engagements": frozenset({"status"}),
        "request_items": frozenset({"status"}),
        "connections": frozenset({"status"}),
        "sync_runs": frozenset(
            {"status", "raw_storage_key", "raw_version_id", "raw_fingerprint", "raw_size_bytes"}
            | {"raw_pulled_at", "source", "snapshot_id", "evidence_version_id"}
            | {"failure_code", "finished_at"}
        ),
        "agent_runs": frozenset(
            {"status", "context_hash", "output", "failure_code", "finished_at"}
        ),
    } == sc.APP_UPDATE_COLUMNS
    assert sc.APP_INSERT_COLUMNS["connections"] == frozenset()
    assert sc.APP_INSERT_COLUMNS["sync_runs"] == frozenset(
        {"id", "tenant_id", "client_entity_id", "connection_id", "engagement_id"}
        | {"request_item_id", "dataset", "period_start", "period_end", "started_by"}
    )
    assert sc.APP_INSERT_COLUMNS["ledger_snapshots"] == frozenset(
        {"id", "tenant_id", "client_entity_id", "period_start", "period_end", "pulled_at"}
        | {"source", "raw_fingerprint", "line_count", "total_debit", "total_credit"}
    )
    assert sc.APP_INSERT_COLUMNS["trial_balance_lines"] == frozenset(
        {"id", "tenant_id", "snapshot_id", "account_code", "account_name", "debit", "credit"}
        | {"source_ref"}
    )
    assert sc.APP_INSERT_COLUMNS["fulfilments"] == frozenset(
        {"id", "tenant_id", "engagement_id", "request_item_id", "evidence_version_id"}
        | {"created_by_kind", "created_by_id"}
    )
    assert sc.APP_INSERT_COLUMNS["agent_runs"] == frozenset(
        {"id", "tenant_id", "agent_id", "spec_version", "engagement_id", "evidence_version_id"}
        | {"initiator_user_id", "source_event_id", "task_scope"}
    )
    assert sc.APP_INSERT_COLUMNS["screening_results"] == frozenset(
        {"id", "tenant_id", "engagement_id", "evidence_version_id", "agent_run_id", "action"}
        | {"confidence", "rationale", "citations", "unverified"}
    )
    assert sc.APP_INSERT_COLUMNS["usage_records"] == frozenset(
        {"id", "tenant_id", "engagement_id", "agent_id", "agent_run_id", "prompt_id"}
        | {"prompt_version", "model", "tier", "input_tokens", "output_tokens", "cost_usd"}
        | {"outcome", "inputs_hash"}
    )
    assert {"ledger_snapshots", "trial_balance_lines", "fulfilments"} <= sc.INSERT_ONLY_TABLES
    assert {"screening_results", "usage_records"} <= sc.INSERT_ONLY_TABLES
    assert "agent_runs" not in sc.INSERT_ONLY_TABLES
    assert sc.APP_INSERT_COLUMNS["engagements"] == frozenset(
        {"id", "tenant_id", "client_id", "client_entity_id", "name"}
        | {"fiscal_period_start", "fiscal_period_end", "created_by"}
    )
    assert sc.APP_INSERT_COLUMNS["clients"] == frozenset({"id", "tenant_id", "name"})
    assert sc.APP_INSERT_COLUMNS["request_items"] == frozenset(
        {"id", "tenant_id", "engagement_id", "request_list_id", "description", "audit_area"}
        | {"created_by"}
    )
    assert sc.APP_INSERT_COLUMNS["engagement_members"] == frozenset(
        {"tenant_id", "engagement_id", "user_id", "role"}
    )


# --- evidence immutability trigger (TASK-009 contract and revision 1) ----------------------------

IMMUTABLE_FUNCTION = "evidence_versions_immutable"
LEDGER_FUNCTION = "ledger_immutable"
RESTORE_EVIDENCE = [
    "DROP TRIGGER IF EXISTS evidence_versions_no_update_or_delete ON evidence_versions",
    "DROP TRIGGER IF EXISTS evidence_versions_no_truncate ON evidence_versions",
    "DROP TRIGGER IF EXISTS zz_evidence_after ON evidence_versions",
    "DROP TRIGGER IF EXISTS zz_evidence_other ON evidence_versions",
    "DROP FUNCTION IF EXISTS zz_evidence_other_fn()",
    "CREATE OR REPLACE FUNCTION evidence_versions_immutable() RETURNS trigger "
    "LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'evidence versions are immutable (ADR-004)' "
    "USING ERRCODE = 'insufficient_privilege'; END $$",
    "CREATE TRIGGER evidence_versions_no_update_or_delete BEFORE UPDATE OR DELETE ON "
    "evidence_versions FOR EACH ROW EXECUTE FUNCTION evidence_versions_immutable()",
    "CREATE TRIGGER evidence_versions_no_truncate BEFORE TRUNCATE ON evidence_versions "
    "FOR EACH STATEMENT EXECUTE FUNCTION evidence_versions_immutable()",
]
ROW_TRIGGER = "evidence_versions_no_update_or_delete"
TRUNCATE_TRIGGER = "evidence_versions_no_truncate"


@pytest.fixture(scope="module")
def evidence_db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


@pytest.fixture
def evidence(evidence_db: sc.Database) -> Iterator[sc.Database]:
    yield evidence_db
    _sql(evidence_db.superuser_dsn, *RESTORE_EVIDENCE)


def _evidence_problems(database: sc.Database) -> list[str]:
    return [m for m in sc.check(database.owner_url, database.app_url) if "evidence" in m]


def _missing(op: str) -> str:
    return (
        f"evidence_versions: no enabled BEFORE {op} trigger calling {IMMUTABLE_FUNCTION} "
        "that raises"
    )


def test_ac20_the_migrated_evidence_triggers_pass_schema_check(evidence: sc.Database) -> None:
    assert sc.IMMUTABLE_TABLES == {
        "evidence_versions": IMMUTABLE_FUNCTION,
        "ledger_snapshots": LEDGER_FUNCTION,
        "trial_balance_lines": LEDGER_FUNCTION,
    }
    assert _evidence_problems(evidence) == []


def test_ac20_a_dropped_truncate_trigger_is_reported(evidence: sc.Database) -> None:
    _sql(evidence.superuser_dsn, f"DROP TRIGGER {TRUNCATE_TRIGGER} ON evidence_versions")
    assert _evidence_problems(evidence) == [_missing("TRUNCATE")]


def test_ac20_a_dropped_update_delete_trigger_reports_both_operations(
    evidence: sc.Database,
) -> None:
    _sql(evidence.superuser_dsn, f"DROP TRIGGER {ROW_TRIGGER} ON evidence_versions")
    assert sorted(_evidence_problems(evidence)) == sorted([_missing("UPDATE"), _missing("DELETE")])


def test_ac20_both_triggers_dropped_reports_all_three_operations(evidence: sc.Database) -> None:
    _sql(
        evidence.superuser_dsn,
        f"DROP TRIGGER {ROW_TRIGGER} ON evidence_versions",
        f"DROP TRIGGER {TRUNCATE_TRIGGER} ON evidence_versions",
    )
    assert sorted(_evidence_problems(evidence)) == sorted(
        [_missing("UPDATE"), _missing("DELETE"), _missing("TRUNCATE")]
    )


def test_ac20_a_disabled_trigger_is_reported(evidence: sc.Database) -> None:
    _sql(
        evidence.superuser_dsn, f"ALTER TABLE evidence_versions DISABLE TRIGGER {TRUNCATE_TRIGGER}"
    )
    assert _evidence_problems(evidence) == [_missing("TRUNCATE")]


def test_ac20_a_replica_only_trigger_is_reported(evidence: sc.Database) -> None:
    _sql(
        evidence.superuser_dsn,
        f"ALTER TABLE evidence_versions ENABLE REPLICA TRIGGER {TRUNCATE_TRIGGER}",
    )
    assert _evidence_problems(evidence) == [_missing("TRUNCATE")]


def test_ac20_an_always_enabled_trigger_passes(evidence: sc.Database) -> None:
    _sql(
        evidence.superuser_dsn,
        f"ALTER TABLE evidence_versions ENABLE ALWAYS TRIGGER {TRUNCATE_TRIGGER}",
        f"ALTER TABLE evidence_versions ENABLE ALWAYS TRIGGER {ROW_TRIGGER}",
    )
    assert _evidence_problems(evidence) == []


def test_ac20_a_trigger_function_that_no_longer_raises_is_reported(evidence: sc.Database) -> None:
    _sql(
        evidence.superuser_dsn,
        "CREATE OR REPLACE FUNCTION evidence_versions_immutable() RETURNS trigger "
        "LANGUAGE plpgsql AS $$ BEGIN RETURN NEW; END $$",
    )
    assert sorted(_evidence_problems(evidence)) == sorted(
        [_missing("UPDATE"), _missing("DELETE"), _missing("TRUNCATE")]
    )


def test_ac20_a_trigger_that_returns_after_raising_is_reported(evidence: sc.Database) -> None:
    _sql(
        evidence.superuser_dsn,
        "CREATE OR REPLACE FUNCTION evidence_versions_immutable() RETURNS trigger "
        "LANGUAGE plpgsql AS $$ BEGIN IF false THEN RAISE EXCEPTION 'never'; END IF; "
        "RETURN NEW; END $$",
    )
    assert len(_evidence_problems(evidence)) == 3


def test_ac20_an_after_trigger_does_not_count(evidence: sc.Database) -> None:
    _sql(
        evidence.superuser_dsn,
        f"DROP TRIGGER {ROW_TRIGGER} ON evidence_versions",
        "CREATE TRIGGER zz_evidence_after AFTER UPDATE OR DELETE ON evidence_versions "
        f"FOR EACH ROW EXECUTE FUNCTION {IMMUTABLE_FUNCTION}()",
    )
    assert sorted(_evidence_problems(evidence)) == sorted([_missing("UPDATE"), _missing("DELETE")])


def test_ac20_a_trigger_calling_another_function_does_not_count(evidence: sc.Database) -> None:
    _sql(
        evidence.superuser_dsn,
        f"DROP TRIGGER {TRUNCATE_TRIGGER} ON evidence_versions",
        "CREATE FUNCTION zz_evidence_other_fn() RETURNS trigger LANGUAGE plpgsql AS "
        "$$ BEGIN RAISE EXCEPTION 'other'; END $$",
        "CREATE TRIGGER zz_evidence_other BEFORE TRUNCATE ON evidence_versions "
        "FOR EACH STATEMENT EXECUTE FUNCTION zz_evidence_other_fn()",
    )
    assert _evidence_problems(evidence) == [_missing("TRUNCATE")]


# --- ledger immutability triggers (TASK-010a contract, migration 0009) ---------------------------

LEDGER_TABLES = ["ledger_snapshots", "trial_balance_lines"]
RESTORE_LEDGER = [
    "DROP TRIGGER IF EXISTS ledger_snapshots_no_update_or_delete ON ledger_snapshots",
    "DROP TRIGGER IF EXISTS ledger_snapshots_no_truncate ON ledger_snapshots",
    "DROP TRIGGER IF EXISTS trial_balance_lines_no_update_or_delete ON trial_balance_lines",
    "DROP TRIGGER IF EXISTS trial_balance_lines_no_truncate ON trial_balance_lines",
    "DROP TRIGGER IF EXISTS zz_ledger_after ON ledger_snapshots",
    "CREATE OR REPLACE FUNCTION ledger_immutable() RETURNS trigger LANGUAGE plpgsql AS "
    "$$ BEGIN RAISE EXCEPTION 'ledger snapshots are immutable (ADR-004)' "
    "USING ERRCODE = 'insufficient_privilege'; END $$",
    "CREATE TRIGGER ledger_snapshots_no_update_or_delete BEFORE UPDATE OR DELETE ON "
    "ledger_snapshots FOR EACH ROW EXECUTE FUNCTION ledger_immutable()",
    "CREATE TRIGGER ledger_snapshots_no_truncate BEFORE TRUNCATE ON ledger_snapshots "
    "FOR EACH STATEMENT EXECUTE FUNCTION ledger_immutable()",
    "CREATE TRIGGER trial_balance_lines_no_update_or_delete BEFORE UPDATE OR DELETE ON "
    "trial_balance_lines FOR EACH ROW EXECUTE FUNCTION ledger_immutable()",
    "CREATE TRIGGER trial_balance_lines_no_truncate BEFORE TRUNCATE ON trial_balance_lines "
    "FOR EACH STATEMENT EXECUTE FUNCTION ledger_immutable()",
]


@pytest.fixture
def ledger(evidence_db: sc.Database) -> Iterator[sc.Database]:
    yield evidence_db
    _sql(evidence_db.superuser_dsn, *RESTORE_LEDGER)


def _ledger_problems(database: sc.Database) -> list[str]:
    return [
        m
        for m in sc.check(database.owner_url, database.app_url)
        if m.startswith(("ledger_snapshots:", "trial_balance_lines:"))
    ]


def _ledger_missing(table: str, op: str) -> str:
    return f"{table}: no enabled BEFORE {op} trigger calling {LEDGER_FUNCTION} that raises"


def test_ac20_the_migrated_ledger_triggers_pass_schema_check(ledger: sc.Database) -> None:
    assert _ledger_problems(ledger) == []
    assert sc.check(ledger.owner_url, ledger.app_url) == []


@pytest.mark.parametrize("table", LEDGER_TABLES)
def test_ac20_a_dropped_ledger_truncate_trigger_is_reported(
    ledger: sc.Database, table: str
) -> None:
    _sql(ledger.superuser_dsn, f"DROP TRIGGER {table}_no_truncate ON {table}")
    assert _ledger_problems(ledger) == [_ledger_missing(table, "TRUNCATE")]


@pytest.mark.parametrize("table", LEDGER_TABLES)
def test_ac20_a_dropped_ledger_update_delete_trigger_reports_both_operations(
    ledger: sc.Database, table: str
) -> None:
    _sql(ledger.superuser_dsn, f"DROP TRIGGER {table}_no_update_or_delete ON {table}")
    assert sorted(_ledger_problems(ledger)) == sorted(
        [_ledger_missing(table, "UPDATE"), _ledger_missing(table, "DELETE")]
    )


@pytest.mark.parametrize("table", LEDGER_TABLES)
def test_ac20_a_disabled_ledger_trigger_is_reported(ledger: sc.Database, table: str) -> None:
    _sql(ledger.superuser_dsn, f"ALTER TABLE {table} DISABLE TRIGGER {table}_no_truncate")
    assert _ledger_problems(ledger) == [_ledger_missing(table, "TRUNCATE")]


def test_ac20_a_ledger_trigger_function_that_no_longer_raises_is_reported(
    ledger: sc.Database,
) -> None:
    _sql(
        ledger.superuser_dsn,
        "CREATE OR REPLACE FUNCTION ledger_immutable() RETURNS trigger LANGUAGE plpgsql AS "
        "$$ BEGIN RETURN NULL; END $$",
    )
    assert len(_ledger_problems(ledger)) == 6


def test_ac20_an_after_trigger_does_not_count_for_the_ledger(ledger: sc.Database) -> None:
    _sql(
        ledger.superuser_dsn,
        "DROP TRIGGER ledger_snapshots_no_update_or_delete ON ledger_snapshots",
        "CREATE TRIGGER zz_ledger_after AFTER UPDATE OR DELETE ON ledger_snapshots "
        "FOR EACH ROW EXECUTE FUNCTION ledger_immutable()",
    )
    assert sorted(_ledger_problems(ledger)) == sorted(
        [
            _ledger_missing("ledger_snapshots", "UPDATE"),
            _ledger_missing("ledger_snapshots", "DELETE"),
        ]
    )


@pytest.mark.parametrize("table", ["ledger_snapshots", "trial_balance_lines", "fulfilments"])
def test_ac20_a_granted_update_on_an_insert_only_new_table_is_reported(
    ledger: sc.Database, table: str
) -> None:
    _sql(ledger.superuser_dsn, f"GRANT UPDATE ON {table} TO abacus_app")
    try:
        problems = [
            m for m in sc.check(ledger.owner_url, ledger.app_url) if m.startswith(f"{table}:")
        ]
        assert problems
    finally:
        _sql(ledger.superuser_dsn, f"REVOKE UPDATE ON {table} FROM abacus_app")


def test_ac20_a_wider_update_grant_on_sync_runs_is_reported(ledger: sc.Database) -> None:
    _sql(ledger.superuser_dsn, "GRANT UPDATE (period_start) ON sync_runs TO abacus_app")
    try:
        problems = [m for m in sc.check(ledger.owner_url, ledger.app_url) if "sync_runs" in m]
        assert any("may UPDATE" in m for m in problems)
    finally:
        _sql(ledger.superuser_dsn, "REVOKE UPDATE (period_start) ON sync_runs FROM abacus_app")


def test_ac20_an_insert_grant_on_connections_is_reported(ledger: sc.Database) -> None:
    _sql(ledger.superuser_dsn, "GRANT INSERT (provider) ON connections TO abacus_app")
    try:
        problems = [m for m in sc.check(ledger.owner_url, ledger.app_url) if "connections" in m]
        assert problems
    finally:
        _sql(ledger.superuser_dsn, "REVOKE INSERT (provider) ON connections FROM abacus_app")
