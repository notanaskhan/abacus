"""W-02-T06 (TASK-7605; W-02 §4.2; SPEC-653; DEC-4605): migration 0850.

Row acceptance: "up/down/up passes, session_items stays insert-only, and a soft-deleted session
keeps its items, runs and trace."
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Iterator

import asyncpg
import pytest

from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import migrate, provisioned_database

from .agent_tests.support import Person, Seeder


@pytest.fixture(scope="module")
def private_db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


async def _session(seeder: Seeder) -> tuple[Person, uuid.UUID]:
    tenant_id = await seeder.firm()
    who = await seeder.person(tenant_id)
    session_id = uuid.uuid4()
    await seeder.run(
        "INSERT INTO workbench_sessions (id, tenant_id, title, owner_user_id, origin) "
        "VALUES ($1, $2, 'TY2025 season progress by office', $3, 'manual')",
        session_id,
        tenant_id,
        who.user_id,
    )
    return who, session_id


async def _item(seeder: Seeder, who: Person, session_id: uuid.UUID, seq: int, kind: str) -> None:
    await seeder.run(
        "INSERT INTO session_items (tenant_id, session_id, seq, kind, payload, actor_kind, "
        "actor_id, classification) VALUES ($1, $2, $3, $4, $5, 'human', $6, 'internal')",
        who.tenant_id,
        session_id,
        seq,
        kind,
        json.dumps({"v": 1}),
        str(who.user_id),
    )


def test_a_new_session_is_auto_titled(private_db: sc.Database) -> None:
    seeder = Seeder(private_db.superuser_dsn)
    _, session_id = asyncio.run(_session(seeder))
    assert (
        asyncio.run(
            seeder.value("SELECT title_source FROM workbench_sessions WHERE id = $1", session_id)
        )
        == "auto"
    )


def test_ac_l4_a_manual_title_needs_its_rename_attribution(private_db: sc.Database) -> None:
    seeder = Seeder(private_db.superuser_dsn)
    who, session_id = asyncio.run(_session(seeder))
    with pytest.raises(asyncpg.CheckViolationError):
        asyncio.run(
            seeder.run(
                "UPDATE workbench_sessions SET title_source = 'manual' WHERE id = $1", session_id
            )
        )
    with pytest.raises(asyncpg.CheckViolationError):
        asyncio.run(
            seeder.run(
                "UPDATE workbench_sessions SET renamed_by = $2 WHERE id = $1",
                session_id,
                who.user_id,
            )
        )
    asyncio.run(
        seeder.run(
            "UPDATE workbench_sessions SET title = 'Season by office', title_source = 'manual', "
            "renamed_by = $2, renamed_at = now() WHERE id = $1",
            session_id,
            who.user_id,
        )
    )


@pytest.mark.parametrize("kind", ["context_added", "context_removed", "drill", "notice"])
def test_item_kinds_widened(private_db: sc.Database, kind: str) -> None:
    seeder = Seeder(private_db.superuser_dsn)
    who, session_id = asyncio.run(_session(seeder))
    asyncio.run(_item(seeder, who, session_id, 1, kind))


def test_an_unknown_item_kind_is_refused(private_db: sc.Database) -> None:
    seeder = Seeder(private_db.superuser_dsn)
    who, session_id = asyncio.run(_session(seeder))
    with pytest.raises(asyncpg.CheckViolationError):
        asyncio.run(_item(seeder, who, session_id, 1, "context_edited"))


def test_items_stay_insert_only(private_db: sc.Database) -> None:
    seeder = Seeder(private_db.superuser_dsn)
    who, session_id = asyncio.run(_session(seeder))
    asyncio.run(_item(seeder, who, session_id, 1, "context_added"))
    with pytest.raises(asyncpg.CheckViolationError, match="insert-only"):
        asyncio.run(
            seeder.run("UPDATE session_items SET seq = 2 WHERE session_id = $1", session_id)
        )


def test_a_soft_deleted_session_keeps_its_items(private_db: sc.Database) -> None:
    seeder = Seeder(private_db.superuser_dsn)
    who, session_id = asyncio.run(_session(seeder))
    asyncio.run(_item(seeder, who, session_id, 1, "user_message"))
    with pytest.raises(asyncpg.CheckViolationError):  # deleted_by without deleted_at
        asyncio.run(
            seeder.run(
                "UPDATE workbench_sessions SET deleted_by = $2 WHERE id = $1",
                session_id,
                who.user_id,
            )
        )
    asyncio.run(
        seeder.run(
            "UPDATE workbench_sessions SET deleted_at = now(), deleted_by = $2 WHERE id = $1",
            session_id,
            who.user_id,
        )
    )
    count = asyncio.run(
        seeder.value("SELECT count(*) FROM session_items WHERE session_id = $1", session_id)
    )
    assert count == 1


@pytest.mark.parametrize(
    "index", ["workbench_sessions_client_scope", "workbench_sessions_title_trgm"]
)
def test_list_indexes_exist(private_db: sc.Database, index: str) -> None:
    seeder = Seeder(private_db.superuser_dsn)
    assert asyncio.run(seeder.value("SELECT to_regclass($1) IS NOT NULL", f"public.{index}"))


def test_up_down_up(private_db: sc.Database) -> None:
    seeder = Seeder(private_db.superuser_dsn)
    column = (
        "SELECT count(*) FROM information_schema.columns "
        "WHERE table_name = 'workbench_sessions' AND column_name = 'title_source'"
    )
    migrate(private_db.owner_url, "0842", down=True)
    assert asyncio.run(seeder.value(column)) == 0
    migrate(private_db.owner_url, "head")
    assert asyncio.run(seeder.value(column)) == 1
