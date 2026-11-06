"""P-10-T04 (TASK-5113; P-10 §4.2; ADR-235; SPEC-647 AC-S5): migration 0682.

Row acceptance: "RLS is forced, session_items is insert-only, and a soft-deleted session keeps its
items and runs."
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
        "VALUES ($1, $2, 'TY2025 season progress', $3, 'manual')",
        session_id,
        tenant_id,
        who.user_id,
    )
    await seeder.run(
        "INSERT INTO session_items (tenant_id, session_id, seq, kind, payload, actor_kind, "
        "actor_id, classification) "
        "VALUES ($1, $2, 1, 'user_message', $3, 'human', $4, 'internal')",
        tenant_id,
        session_id,
        json.dumps({"v": 1}),
        str(who.user_id),
    )
    return who, session_id


@pytest.mark.parametrize("table", ["workbench_sessions", "session_items"])
def test_rls_is_forced(private_db: sc.Database, table: str) -> None:
    forced = asyncio.run(
        Seeder(private_db.superuser_dsn).value(
            "SELECT relforcerowsecurity AND relrowsecurity FROM pg_class WHERE relname = $1", table
        )
    )
    assert forced is True


@pytest.mark.parametrize("sql", ["UPDATE session_items SET seq = 2", "DELETE FROM session_items"])
def test_items_are_insert_only(private_db: sc.Database, sql: str) -> None:
    seeder = Seeder(private_db.superuser_dsn)
    _, session_id = asyncio.run(_session(seeder))
    with pytest.raises(asyncpg.CheckViolationError, match="insert-only"):
        asyncio.run(seeder.run(f"{sql} WHERE session_id = $1", session_id))


def test_a_soft_deleted_session_keeps_its_items(private_db: sc.Database) -> None:
    seeder = Seeder(private_db.superuser_dsn)
    _, session_id = asyncio.run(_session(seeder))
    asyncio.run(
        seeder.run("UPDATE workbench_sessions SET deleted_at = now() WHERE id = $1", session_id)
    )
    assert (
        asyncio.run(
            seeder.value("SELECT count(*) FROM session_items WHERE session_id = $1", session_id)
        )
        == 1
    )
    with pytest.raises(asyncpg.CheckViolationError, match="soft-deleted"):
        asyncio.run(seeder.run("DELETE FROM workbench_sessions WHERE id = $1", session_id))


def test_an_item_needs_its_schema_version(private_db: sc.Database) -> None:
    seeder = Seeder(private_db.superuser_dsn)
    who, session_id = asyncio.run(_session(seeder))
    with pytest.raises(asyncpg.CheckViolationError):
        asyncio.run(
            seeder.run(
                "INSERT INTO session_items (tenant_id, session_id, seq, kind, payload, "
                "actor_kind, actor_id, classification) "
                "VALUES ($1, $2, 2, 'notice', '{}', 'system', 'x', 'internal')",
                who.tenant_id,
                session_id,
            )
        )


def test_down_then_up(private_db: sc.Database) -> None:
    seeder = Seeder(private_db.superuser_dsn)
    migrate(private_db.owner_url, "0681", down=True)
    assert not asyncio.run(
        seeder.value("SELECT to_regclass('public.workbench_sessions') IS NOT NULL")
    )
    migrate(private_db.owner_url, "head")
    assert asyncio.run(seeder.value("SELECT to_regclass('public.workbench_sessions') IS NOT NULL"))
