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
    return sc.check(db.owner_url, db.app_url)


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
    "CREATE TABLE outbox (id uuid PRIMARY KEY, tenant_id uuid NOT NULL, event_type text, "
    "payload jsonb, published_at timestamptz, attempts int NOT NULL DEFAULT 0, last_error text)"
)
AUDIT_DDL = "CREATE TABLE audit_events (id uuid PRIMARY KEY, tenant_id uuid NOT NULL, action text)"
RELAY_OK = [
    "GRANT SELECT ON outbox TO abacus_relay",
    "GRANT UPDATE (published_at, attempts, last_error) ON outbox TO abacus_relay",
]


def _protect(table: str) -> list[str]:
    return [
        ENABLE.format(t=table),
        FORCE.format(t=table),
        POLICY.format(t=table),
        f"REVOKE UPDATE, DELETE ON {table} FROM abacus_app",
    ]


def _relay_tables() -> list[str]:
    return [OUTBOX_DDL, *_protect("outbox"), AUDIT_DDL, *_protect("audit_events"), *RELAY_OK]


@pytest.fixture
def relay_db(db: Cluster) -> Iterator[Cluster]:
    yield db
    _sql(
        db.admin,
        "DROP TABLE IF EXISTS outbox, audit_events CASCADE",
        "ALTER ROLE abacus_relay NOSUPERUSER NOCREATEROLE NOCREATEDB",
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
