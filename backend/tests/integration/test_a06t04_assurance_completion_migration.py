"""A-06-T04 (TASK-2916; A-06 §3 F1, F2, F4; SPEC-642 AC-1, AC-5; DEC-1963): migration 0644.

A concluded or communicated deficiency names its severity and a person's decision on its own
card; a SUM snapshot is insert-only; passing a misstatement on SUM names who and why; a
consultation is concluded only by the person consulted; one finding per issue; down to 0643 and
up again with forced RLS.

The rows name no real work item: a refusal from a CHECK or a guard comes before the foreign keys.
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

BEFORE = "0643"
TABLES = (
    "audit_findings",
    "deficiencies",
    "audit_misstatements",
    "sum_snapshots",
    "consultations",
)


@pytest.fixture(scope="module")
def private_db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


def _value(database: sc.Database, sql: str, *args: object) -> object:
    return asyncio.run(Seeder(database.superuser_dsn).value(sql, *args))


async def _as(dsn: str, kind: str, actor: str, sql: str, *args: object) -> None:
    await Seeder(dsn).as_actor(cast(uuid.UUID, args[0]), (kind, actor), sql, *args)


def _deficiency(
    status: str, severity: str | None, decision: uuid.UUID | None
) -> tuple[str, tuple[object, ...]]:
    return (
        "INSERT INTO deficiencies (tenant_id, engagement_id, work_item_id, finding_id, status, "
        "severity_concluded, decision_card_id, decision_id) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)",
        (
            uuid.uuid4(),
            uuid.uuid4(),
            uuid.uuid4(),
            uuid.uuid4(),
            status,
            severity,
            uuid.uuid4() if decision is not None else None,
            decision,
        ),
    )


def test_0644_goes_down_and_up_with_forced_rls(private_db: sc.Database) -> None:
    migrate(private_db.owner_url, BEFORE, down=True)
    for table in TABLES:
        assert _value(private_db, "SELECT to_regclass($1) IS NULL", table), table
    migrate(private_db.owner_url, "head")
    for table in TABLES:
        assert _value(
            private_db,
            "SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE relname = $1",
            table,
        ), table


@pytest.mark.parametrize("status", ["concluded", "communicated"])
def test_a_concluded_deficiency_needs_its_severity_and_decision(
    private_db: sc.Database, status: str
) -> None:
    sql, args = _deficiency(status, None, None)
    with pytest.raises(asyncpg.CheckViolationError, match="names its severity"):
        asyncio.run(_as(private_db.superuser_dsn, "human", str(uuid.uuid4()), sql, *args))


def test_a_decision_not_on_the_deficiencys_card_is_refused(private_db: sc.Database) -> None:
    sql, args = _deficiency("concluded", "significant_deficiency", uuid.uuid4())
    with pytest.raises(asyncpg.CheckViolationError, match="decision on its own card"):
        asyncio.run(_as(private_db.superuser_dsn, "human", str(uuid.uuid4()), sql, *args))


def test_a_proposed_deficiency_needs_no_decision(private_db: sc.Database) -> None:
    sql, args = _deficiency("proposed", None, None)
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        asyncio.run(_as(private_db.superuser_dsn, "agent", "agent-run", sql, *args))


def test_passing_on_sum_names_who_and_why(private_db: sc.Database) -> None:
    sql = (
        "INSERT INTO audit_misstatements (tenant_id, engagement_id, work_item_id, ref, type, "
        "status, amount, column_set) VALUES ($1, $2, $3, 'PAJE-1', 'projected', "
        "'passed_on_sum', 35300, 'ebp_net_assets')"
    )
    args = (uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
    with pytest.raises(asyncpg.CheckViolationError):
        asyncio.run(_as(private_db.superuser_dsn, "human", str(uuid.uuid4()), sql, *args))


def test_sum_snapshots_are_insert_only(private_db: sc.Database) -> None:
    assert not _value(
        private_db, "SELECT has_any_column_privilege('abacus_app', 'sum_snapshots', 'UPDATE')"
    )


@pytest.mark.parametrize("table", TABLES)
def test_the_app_role_never_deletes(private_db: sc.Database, table: str) -> None:
    assert not _value(private_db, "SELECT has_table_privilege('abacus_app', $1, 'DELETE')", table)
