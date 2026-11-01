"""A-06-T03 (TASK-2915; A-06 §3 F1, §4.2; SPEC-642 AC-1, AC-2; DEC-1962): migration 0643.

Row acceptance: an unbalanced entry fails at commit with `unbalanced_entry`, a posting status is
refused by `pe_posting_dormant`, an attest client's entry is `review_required`, decisions and
batches are insert-only and a person's own, and lines lock once the entry is approved.

The rows name no real work item: a refusal from a CHECK or a guard comes before the foreign
keys, and a row that passes them fails on its foreign key instead.
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

BEFORE = "0642"
TABLES = (
    "proposed_entries",
    "proposed_entry_lines",
    "proposed_entry_decisions",
    "approval_batches",
)
INSERT_ONLY = ("proposed_entry_decisions", "approval_batches")


@pytest.fixture(scope="module")
def private_db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


def _value(database: sc.Database, sql: str, *args: object) -> object:
    return asyncio.run(Seeder(database.superuser_dsn).value(sql, *args))


async def _as(dsn: str, kind: str, actor: str, sql: str, *args: object) -> None:
    await Seeder(dsn).as_actor(cast(uuid.UUID, args[0]), (kind, actor), sql, *args)


def _entry(status: str, *, attest: bool, result: str) -> tuple[str, tuple[object, ...]]:
    return (
        "INSERT INTO proposed_entries (tenant_id, engagement_id, work_item_id, kind, number, ref, "
        "threshold_result, is_attest_client, status, created_by_kind, created_by_id) "
        "VALUES ($1, $2, $3, 'aje', 1, 'AJE-1', $4, $5, $6, 'human', 'someone')",
        (uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), result, attest, status),
    )


def test_0643_goes_down_and_up_with_forced_rls(private_db: sc.Database) -> None:
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


@pytest.mark.parametrize("status", ["posted", "failed_post", "reversed"])
def test_ac_no_entry_is_ever_posted(private_db: sc.Database, status: str) -> None:
    sql, args = _entry(status, attest=False, result="within_threshold")
    with pytest.raises(asyncpg.CheckViolationError, match="pe_posting_dormant"):
        asyncio.run(_as(private_db.superuser_dsn, "human", str(uuid.uuid4()), sql, *args))


def test_ac_an_attest_clients_entry_is_review_required(private_db: sc.Database) -> None:
    sql, args = _entry("proposed", attest=True, result="within_threshold")
    with pytest.raises(asyncpg.CheckViolationError, match="pe_attest_review_required"):
        asyncio.run(_as(private_db.superuser_dsn, "human", str(uuid.uuid4()), sql, *args))
    sql, args = _entry("proposed", attest=True, result="review_required")
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        asyncio.run(_as(private_db.superuser_dsn, "human", str(uuid.uuid4()), sql, *args))


def test_a_line_carries_a_debit_or_a_credit_never_both(private_db: sc.Database) -> None:
    sql = (
        "INSERT INTO proposed_entry_lines (tenant_id, engagement_id, work_item_id, entry_id, "
        "line_no, account_code, debit, credit) VALUES ($1, $2, $3, $4, 1, '1250', 10, 10)"
    )
    args = (uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
    with pytest.raises(asyncpg.CheckViolationError, match="pe_line_one_side"):
        asyncio.run(_as(private_db.superuser_dsn, "human", str(uuid.uuid4()), sql, *args))


@pytest.mark.parametrize("kind", ["agent", "system"])
def test_a_decision_is_a_persons(private_db: sc.Database, kind: str) -> None:
    sql = (
        "INSERT INTO proposed_entry_decisions (tenant_id, engagement_id, work_item_id, entry_id, "
        "decision, actor_principal, channel, seen_version, actor_kind) "
        "VALUES ($1, $2, $3, $4, 'approved', 'firm_user', 'app', 1, $5)"
    )
    args = (uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), kind)
    with pytest.raises(asyncpg.CheckViolationError):
        asyncio.run(_as(private_db.superuser_dsn, kind, "actor", sql, *args))


def test_a_batch_names_the_sessions_own_person(private_db: sc.Database) -> None:
    sql = (
        "INSERT INTO approval_batches (tenant_id, engagement_id, work_item_id, entry_ids, "
        "approver_user_id, label) VALUES ($1, $2, $3, ARRAY[$4::uuid], $5, 'Approved by RM')"
    )
    args = (uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
    with pytest.raises(asyncpg.CheckViolationError, match="approval_batches_own_person"):
        asyncio.run(_as(private_db.superuser_dsn, "human", str(uuid.uuid4()), sql, *args))


@pytest.mark.parametrize("table", INSERT_ONLY)
def test_decisions_and_batches_are_insert_only(private_db: sc.Database, table: str) -> None:
    assert not _value(
        private_db, "SELECT has_any_column_privilege('abacus_app', $1, 'UPDATE')", table
    )
    assert not _value(private_db, "SELECT has_table_privilege('abacus_app', $1, 'DELETE')", table)
