"""N-04-T03 (TASK-3002; DEC-2052): migration 0650 `notices_v1`.

Row acceptance: "the migration merges in the Oct 21 batch; insert-only triggers and human-actor
CHECKs are tested." Down to 0644 removes the eleven tables and the v1 columns, and up again
restores them with forced row-level security. The nine insert-only tables refuse UPDATE, DELETE
and TRUNCATE at the database, for every role. A sent record, an agency reply, a person's field
value or confirmation and a note are refused outside a person's session. A TIN is sealed, never
plain. The status CHECKs are the status vocabulary's codes.

The rows name no real notice: a refusal from a CHECK or a trigger comes before the foreign keys,
and a row that passes them fails on its foreign key instead, which shows the guard let it through.
"""

from __future__ import annotations

import asyncio
import importlib.util
import uuid
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from typing import cast

import asyncpg
import pytest
import yaml

from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import migrate, provisioned_database

from .agent_tests.support import Seeder

BEFORE = "0644"
REPO = Path(__file__).resolve().parents[3]


def _migration() -> ModuleType:
    path = REPO / "backend" / "migrations" / "versions" / "0650_notices_v1.py"
    spec = importlib.util.spec_from_file_location("notices_v1_0650", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


M = _migration()
TABLES = (*M.IMMUTABLE, *M.MUTABLE)


@pytest.fixture(scope="module")
def private_db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


def _value(database: sc.Database, sql: str) -> object:
    return asyncio.run(Seeder(database.superuser_dsn).value(sql))


async def _as(dsn: str, kind: str, actor: str, sql: str, *args: object) -> None:
    await Seeder(dsn).as_actor(cast(uuid.UUID, args[0]), (kind, actor), sql, *args)


def _sent(kind: str) -> tuple[str, tuple[object, ...]]:
    return (
        "INSERT INTO notice_sent_records (tenant_id, work_item_id, response_id, channel, "
        "sent_on, follow_up_on, recorded_by, recorded_actor_kind) "
        "VALUES ($1, $2, $3, 'dut', DATE '2026-09-17', DATE '2026-11-16', $4, $5)",
        (uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), kind),
    )


def _reply(kind: str) -> tuple[str, tuple[object, ...]]:
    return (
        "INSERT INTO notice_agency_replies (tenant_id, work_item_id, outcome, closed_on, "
        "recorded_by, recorded_actor_kind) VALUES ($1, $2, 'resolved', DATE '2026-12-02', $3, $4)",
        (uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), kind),
    )


def _field(
    value_type: str, text: str | None, sealed: bytes | None
) -> tuple[str, tuple[object, ...]]:
    return (
        "INSERT INTO notice_field_values (tenant_id, owner_type, owner_id, field_key, value_type, "
        "value_text, value_sealed, origin, recorded_actor_kind) "
        "VALUES ($1, 'intake', $2, 'taxpayer.tin', $3, $4, $5, 'code_map', 'system')",
        (uuid.uuid4(), uuid.uuid4(), value_type, text, sealed),
    )


def test_ac_0650_goes_down_and_up_with_forced_rls(private_db: sc.Database) -> None:
    migrate(private_db.owner_url, BEFORE, down=True)
    for table in TABLES:
        assert _value(private_db, f"SELECT to_regclass('{table}') IS NULL"), table
    assert not _value(
        private_db,
        "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
        "WHERE table_name = 'notices' AND column_name = 'status')",
    )
    migrate(private_db.owner_url, "head")
    for table in TABLES:
        forced = asyncio.run(
            Seeder(private_db.superuser_dsn).value(
                "SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE relname = $1",
                table,
            )
        )
        assert forced, table


@pytest.mark.parametrize("table", M.IMMUTABLE)
def test_ac_the_nine_records_are_insert_only_for_the_app(
    private_db: sc.Database, table: str
) -> None:
    assert not _value(
        private_db, f"SELECT has_any_column_privilege('abacus_app', '{table}', 'UPDATE')"
    )
    assert not _value(private_db, f"SELECT has_table_privilege('abacus_app', '{table}', 'DELETE')")
    assert _value(
        private_db, f"SELECT has_any_column_privilege('abacus_app', '{table}', 'INSERT')"
    )


@pytest.mark.parametrize("table", M.IMMUTABLE)
def test_ac_the_triggers_refuse_update_delete_and_truncate_for_every_role(
    private_db: sc.Database, table: str
) -> None:
    triggers = asyncio.run(
        Seeder(private_db.superuser_dsn).value(
            "SELECT array_agg(tgname::text ORDER BY tgname) FROM pg_trigger t "
            "JOIN pg_class c ON c.oid = t.tgrelid WHERE c.relname = $1 AND NOT t.tgisinternal",
            table,
        )
    )
    assert set(cast(list[str], triggers)) >= {f"{table}_immutable", f"{table}_no_truncate"}
    with pytest.raises(asyncpg.InsufficientPrivilegeError, match="insert-only"):
        asyncio.run(Seeder(private_db.superuser_dsn).value(f"TRUNCATE {table}"))


@pytest.mark.parametrize("kind", ["agent", "system"])
def test_ac_a_sent_record_is_only_a_persons(private_db: sc.Database, kind: str) -> None:
    sql, args = _sent(kind)
    with pytest.raises(asyncpg.CheckViolationError):
        asyncio.run(_as(private_db.superuser_dsn, kind, "run", sql, *args))


def test_a_sent_record_claiming_human_in_an_agent_session_is_refused(
    private_db: sc.Database,
) -> None:
    sql, args = _sent("human")
    with pytest.raises(asyncpg.CheckViolationError):
        asyncio.run(_as(private_db.superuser_dsn, "agent", "run", sql, *args))


def test_a_persons_sent_record_passes_the_check(private_db: sc.Database) -> None:
    sql, args = _sent("human")
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        asyncio.run(_as(private_db.superuser_dsn, "human", str(uuid.uuid4()), sql, *args))


@pytest.mark.parametrize("kind", ["agent", "system"])
def test_ac_an_agency_reply_is_only_a_persons(private_db: sc.Database, kind: str) -> None:
    sql, args = _reply("human")
    with pytest.raises(asyncpg.CheckViolationError):
        asyncio.run(_as(private_db.superuser_dsn, kind, "run", sql, *args))


def test_ac_a_tin_is_sealed_never_plain(private_db: sc.Database) -> None:
    sql, args = _field("tin", "123456789", None)
    with pytest.raises(asyncpg.CheckViolationError):
        asyncio.run(_as(private_db.superuser_dsn, "system", "intake", sql, *args))
    sql, args = _field("tin", None, b"sealed")
    # Past the CHECKs: the made-up tenant is what stops it.
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        asyncio.run(_as(private_db.superuser_dsn, "system", "intake", sql, *args))


def test_ac_a_confirmation_outside_a_persons_session_is_refused(private_db: sc.Database) -> None:
    sql = (
        "INSERT INTO notice_field_values (tenant_id, owner_type, owner_id, field_key, value_type, "
        "value_text, origin, recorded_actor_kind, confirmed_by, low_confidence) "
        "VALUES ($1, 'intake', $2, 'notice.respond_by', 'date', '2026-10-01', 'code_map', "
        "'system', $3, true)"
    )
    args = (uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
    with pytest.raises(asyncpg.CheckViolationError):
        asyncio.run(_as(private_db.superuser_dsn, "agent", "run", sql, *args))


def test_a_note_outside_a_persons_session_is_refused(private_db: sc.Database) -> None:
    sql = (
        "INSERT INTO notice_notes (tenant_id, work_item_id, body_sealed, author_id) "
        "VALUES ($1, $2, $3, $4)"
    )
    args = (uuid.uuid4(), uuid.uuid4(), b"x", uuid.uuid4())
    with pytest.raises(asyncpg.CheckViolationError):
        asyncio.run(_as(private_db.superuser_dsn, "agent", "run", sql, *args))


def test_a_recommendation_needs_a_live_agent_stage(private_db: sc.Database) -> None:
    sql = (
        "INSERT INTO notice_analyses (tenant_id, work_item_id, version, status, analysis_kind, "
        "engine_name, engine_version, inputs_hash, agent_stage, recommended_position) "
        "VALUES ($1, $2, 1, 'ready', 'underreporter_comparison', 'notices', '1', $3, 'shadow', "
        "'agree')"
    )
    args = (uuid.uuid4(), uuid.uuid4(), "a" * 64)
    with pytest.raises(asyncpg.CheckViolationError):
        asyncio.run(_as(private_db.superuser_dsn, "system", "analysis", sql, *args))


@pytest.mark.parametrize("table", TABLES)
def test_the_app_role_never_deletes(private_db: sc.Database, table: str) -> None:
    assert not _value(private_db, f"SELECT has_table_privilege('abacus_app', '{table}', 'DELETE')")


def test_the_notice_subtype_updates_its_v1_columns_only(private_db: sc.Database) -> None:
    for column in ("status", "position", "row_version", "assignee_user_id"):
        assert _value(
            private_db,
            f"SELECT has_column_privilege('abacus_app', 'notices', '{column}', 'UPDATE')",
        ), column
    for column in ("work_item_id", "engagement_id", "tenant_id", "notice_code", "received_on"):
        assert not _value(
            private_db,
            f"SELECT has_column_privilege('abacus_app', 'notices', '{column}', 'UPDATE')",
        ), column


def test_the_status_checks_are_the_vocabularys_codes() -> None:
    vocabulary = yaml.safe_load(
        (REPO / "docs" / "product" / "status-vocabulary.yaml").read_text(encoding="utf-8")
    )["objects"]
    assert set(M.STATUSES) == set(vocabulary["notice"]["codes"])
    assert set(M.INTAKE_STATUSES) == set(vocabulary["notice_intake"]["codes"])
