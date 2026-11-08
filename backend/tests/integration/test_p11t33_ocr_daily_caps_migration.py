"""P-11-T33 (TASK-6128; DEC-2715): `ocr_daily_caps` (0714).

Only a platform (`system`) session writes a cap; a raise above the 5,000 default names two
different operators (R9); rows are insert-only; RLS is forced; the latest row is the cap.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Iterator

import asyncpg
import pytest

from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import provisioned_database

from .agent_tests.support import Seeder

INSERT = (
    "INSERT INTO ocr_daily_caps (tenant_id, daily_pages, raised_by, second_by, reason) "
    "VALUES ($1, $2, $3, $4, $5) RETURNING id"
)
REASON = "December peak for a large firm"


@pytest.fixture(scope="module")
def db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


async def _as(dsn: str, kind: str, sql: str, *args: object) -> object:
    conn = await asyncpg.connect(dsn)
    try:
        async with conn.transaction():
            await conn.execute(
                "SELECT set_config('app.actor_kind', $1, true), "
                "set_config('app.actor_id', 'platform:ocr_daily_cap', true)",
                kind,
            )
            return await conn.fetchval(sql, *args)
    finally:
        await conn.close()


def _value(database: sc.Database, sql: str, *args: object) -> object:
    return asyncio.run(Seeder(database.superuser_dsn).value(sql, *args))


def test_rls_is_forced_and_the_app_cannot_update_or_delete(db: sc.Database) -> None:
    assert (
        _value(
            db,
            "SELECT relforcerowsecurity AND relrowsecurity FROM pg_class "
            "WHERE relname = 'ocr_daily_caps'",
        )
        is True
    )
    for privilege in ("UPDATE", "DELETE", "TRUNCATE"):
        assert (
            _value(db, "SELECT has_table_privilege('abacus_app', 'ocr_daily_caps', $1)", privilege)
            is False
        ), privilege
    assert (
        _value(
            db,
            "SELECT has_column_privilege('abacus_app', 'ocr_daily_caps', 'set_by_kind', 'INSERT')",
        )
        is False
    )


@pytest.mark.parametrize("kind", ["human", "agent", "client"])
def test_only_a_platform_session_sets_a_cap(db: sc.Database, kind: str) -> None:
    with pytest.raises(asyncpg.CheckViolationError, match="platform_only"):
        asyncio.run(_as(db.superuser_dsn, kind, INSERT, uuid.uuid4(), 3000, "a", None, REASON))


@pytest.mark.parametrize(("second_by"), [None, "founder-a", "FOUNDER-A"])
def test_a_raise_names_two_different_operators(db: sc.Database, second_by: str | None) -> None:
    with pytest.raises(asyncpg.CheckViolationError, match="raise_needs_two"):
        asyncio.run(
            _as(db.superuser_dsn, "system", INSERT, uuid.uuid4(), 12000, "founder-a", second_by,
                REASON)
        )  # fmt: skip


def test_a_raise_with_both_and_a_lowering_with_one_pass_and_never_change(
    db: sc.Database,
) -> None:
    tenant = uuid.uuid4()
    asyncio.run(
        _as(db.superuser_dsn, "system", INSERT, tenant, 12000, "founder-a", "founder-b", REASON)
    )
    lowered = asyncio.run(
        _as(db.superuser_dsn, "system", INSERT, tenant, 2000, "founder-a", None, REASON)
    )
    assert (
        _value(
            db,
            "SELECT daily_pages FROM ocr_daily_caps WHERE tenant_id = $1 "
            "ORDER BY set_at DESC, id LIMIT 1",
            tenant,
        )
        == 2000
    )
    with pytest.raises(asyncpg.PostgresError):
        asyncio.run(
            Seeder(db.superuser_dsn).run(
                "UPDATE ocr_daily_caps SET daily_pages = 99999 WHERE id = $1", lowered
            )
        )


@pytest.mark.parametrize(("pages", "reason"), [(0, REASON), (100001, REASON), (3000, "short")])
def test_bounds_and_a_reason(db: sc.Database, pages: int, reason: str) -> None:
    with pytest.raises(asyncpg.CheckViolationError):
        asyncio.run(_as(db.superuser_dsn, "system", INSERT, uuid.uuid4(), pages, "a", "b", reason))
