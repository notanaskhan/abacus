"""R-02-T07 (TASK-6107; R-02 §3.15 AC-39; ADR-104, DEC-509): migration 0712's download links.

A link is issued to the session's person only, expires 60 seconds after issue (server-set: the
app role cannot supply `issued_at` or `expires_at`), changes only by being used, once, and is never
deleted. Forced RLS keeps it single-tenant."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Iterator

import asyncpg
import pytest

from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import provisioned_database

from .agent_tests.support import Seeder

TABLE = "deliverable_download_links"


@pytest.fixture(scope="module")
def db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


def _value(database: sc.Database, sql: str, *args: object) -> object:
    return asyncio.run(Seeder(database.superuser_dsn).value(sql, *args))


def test_rls_is_forced_and_the_trigger_is_there(db: sc.Database) -> None:
    assert _value(
        db, "SELECT relforcerowsecurity AND relrowsecurity FROM pg_class WHERE relname = $1", TABLE
    )
    assert (
        _value(
            db,
            "SELECT count(*) FROM pg_trigger WHERE tgrelid = $1::regclass "
            "AND tgname = 'deliverable_download_links_once'",
            TABLE,
        )
        == 1
    )


@pytest.mark.parametrize(
    ("privilege", "column", "granted"),
    [
        ("INSERT", "issued_at", False),
        ("INSERT", "expires_at", False),
        ("INSERT", "used_at", False),
        ("UPDATE", "used_at", True),
        ("UPDATE", "expires_at", False),
        ("UPDATE", "user_id", False),
    ],
)
def test_ac39_the_app_role_cannot_stretch_a_link(
    db: sc.Database, privilege: str, column: str, granted: bool
) -> None:
    has = _value(
        db, "SELECT has_column_privilege('abacus_app', $1, $2, $3)", TABLE, column, privilege
    )
    assert has is granted


def test_a_link_is_never_deleted_by_the_app(db: sc.Database) -> None:
    assert _value(db, "SELECT has_table_privilege('abacus_app', $1, 'DELETE')", TABLE) is False


async def _issue(dsn: str, *, actor: str, user: uuid.UUID) -> None:
    conn = await asyncpg.connect(dsn)
    try:
        async with conn.transaction():
            await conn.execute("SELECT set_config('app.actor_id', $1, true)", actor)
            await conn.execute(
                "INSERT INTO deliverable_download_links (tenant_id, deliverable_version_id, "
                "evidence_version_id, contact_id, user_id) VALUES ($1, $2, $3, $4, $5)",
                uuid.uuid4(),
                uuid.uuid4(),
                uuid.uuid4(),
                uuid.uuid4(),
                user,
            )
    finally:
        await conn.close()


def test_a_link_is_issued_to_the_session_s_person_only(db: sc.Database) -> None:
    user = uuid.uuid4()
    with pytest.raises(asyncpg.CheckViolationError):
        asyncio.run(_issue(db.superuser_dsn, actor=str(uuid.uuid4()), user=user))
    # The actor check passes for the person themself; the made-up references fail after it.
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        asyncio.run(_issue(db.superuser_dsn, actor=str(user), user=user))


def test_the_sixty_seconds_are_the_schema_s(db: sc.Database) -> None:
    default = _value(
        db,
        "SELECT pg_get_expr(d.adbin, d.adrelid) FROM pg_attrdef d "
        "JOIN pg_attribute a ON a.attrelid = d.adrelid AND a.attnum = d.adnum "
        "WHERE d.adrelid = $1::regclass AND a.attname = 'expires_at'",
        TABLE,
    )
    assert isinstance(default, str) and "00:01:00" in default
