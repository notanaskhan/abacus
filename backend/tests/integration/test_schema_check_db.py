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
