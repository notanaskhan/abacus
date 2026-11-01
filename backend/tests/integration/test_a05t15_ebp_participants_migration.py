"""A-05-T15 (TASK-2912; A-05 §4.2 M2; DEC-1959): migration 0642 `ebp_participants_testing`.

Row acceptance: "No plaintext SSN or DOB column exists, result rows are insert-only, and a
human-only CHECK refuses an agent writing pass, exception or no_effect." Also: down to 0641
removes the five tables and up restores them with forced row-level security, an import is a
person's, and the app role never deletes.

The guards are tested in a transaction with the session's settings set as `tenant_connection`
sets them; the rows name no real work item, so a row that passes the CHECKs fails on its foreign
key instead, which shows the CHECK let it through.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Iterator
from typing import cast

import asyncpg
import pytest

from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import migrate, provisioned_database

from .agent_tests.support import Seeder

BEFORE = "0641"
TABLES = (
    "ebp_source_imports",
    "ebp_participants",
    "attribute_tests",
    "test_attribute_results",
    "ebp_population_queries",
)
INSERT_ONLY = ("test_attribute_results", "ebp_population_queries")


@pytest.fixture(scope="module")
def private_db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


def _value(database: sc.Database, sql: str) -> object:
    return asyncio.run(Seeder(database.superuser_dsn).value(sql))


async def _as(dsn: str, kind: str, actor: str, sql: str, *args: object) -> None:
    await Seeder(dsn).as_actor(cast(uuid.UUID, args[0]), (kind, actor), sql, *args)


def _result(result: str) -> tuple[str, tuple[object, ...]]:
    return (
        "INSERT INTO test_attribute_results (tenant_id, engagement_id, work_item_id, test_id, "
        "sample_item_id, attribute_key, seq, result) "
        "VALUES ($1, $2, $3, $4, $5, 'hire_date', 1, $6)",
        (uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), result),
    )


def test_0642_goes_down_and_up_with_forced_rls(private_db: sc.Database) -> None:
    migrate(private_db.owner_url, BEFORE, down=True)
    for table in TABLES:
        assert _value(private_db, f"SELECT to_regclass('{table}') IS NULL"), table
    migrate(private_db.owner_url, "head")
    for table in TABLES:
        forced = _value(
            private_db,
            "SELECT relrowsecurity AND relforcerowsecurity FROM pg_class "
            f"WHERE relname = '{table}'",
        )
        assert forced, table


def test_ac_no_plaintext_ssn_or_dob_column_exists(private_db: sc.Database) -> None:
    columns = cast(
        str,
        _value(
            private_db,
            "SELECT string_agg(column_name, ',' ORDER BY column_name) "
            "FROM information_schema.columns WHERE table_name = 'ebp_participants'",
        ),
    ).split(",")
    assert {"ssn_sealed", "ssn_fp", "ssn_last4", "dob_sealed", "dob_fp"} <= set(columns)
    for plain in ("ssn", "dob", "date_of_birth", "social_security_number", "tin"):
        assert plain not in columns


@pytest.mark.parametrize("result", ["pass", "exception", "no_effect"])
def test_ac_an_agent_may_not_conclude_an_attribute(private_db: sc.Database, result: str) -> None:
    sql, args = _result(result)
    with pytest.raises(asyncpg.CheckViolationError, match="human_concludes"):
        asyncio.run(_as(private_db.superuser_dsn, "agent", "agent-run", sql, *args))


@pytest.mark.parametrize("result", ["agent_tested", "needs_human"])
def test_the_agent_may_propose_a_result(private_db: sc.Database, result: str) -> None:
    sql, args = _result(result)
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        asyncio.run(_as(private_db.superuser_dsn, "agent", "agent-run", sql, *args))


def test_a_person_concludes(private_db: sc.Database) -> None:
    sql, args = _result("pass")
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        asyncio.run(_as(private_db.superuser_dsn, "human", str(uuid.uuid4()), sql, *args))


def test_an_import_is_a_persons(private_db: sc.Database) -> None:
    sql = (
        "INSERT INTO ebp_source_imports (tenant_id, engagement_id, work_item_id, "
        "evidence_version_id, kind, sha256, imported_by) "
        "VALUES ($1, $2, $3, $4, 'census', $5, $6)"
    )
    args = (uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), "a" * 64, uuid.uuid4())
    with pytest.raises(asyncpg.CheckViolationError, match="by_a_person"):
        asyncio.run(_as(private_db.superuser_dsn, "agent", "agent-run", sql, *args))


@pytest.mark.parametrize("table", TABLES)
def test_the_app_role_never_deletes(private_db: sc.Database, table: str) -> None:
    assert not _value(private_db, f"SELECT has_table_privilege('abacus_app', '{table}', 'DELETE')")


@pytest.mark.parametrize("table", INSERT_ONLY)
def test_results_and_queries_are_insert_only(private_db: sc.Database, table: str) -> None:
    assert not _value(
        private_db, f"SELECT has_any_column_privilege('abacus_app', '{table}', 'UPDATE')"
    )
