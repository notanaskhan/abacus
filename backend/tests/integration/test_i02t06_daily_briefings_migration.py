"""I-02-T06 (TASK-7614; I-02 §4.2; SPEC-654; DEC-4611): migration 0851, `daily_briefings`.

Row acceptance: "The single-head check passes, RLS isolates two tenants, an update to a ready row
fails, and no column holds a TIN or quoted document text."
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

BEFORE = "0850"


@pytest.fixture(scope="module")
def private_db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


def _app_dsn(database: sc.Database) -> str:
    return database.app_url.replace("postgresql+asyncpg://", "postgresql://")


_SEES = "SELECT 1 / (CASE WHEN (SELECT count(*) FROM daily_briefings) = $1 THEN 1 ELSE 0 END)"


def _app_sees(database: sc.Database, tenant_id: uuid.UUID, rows: int) -> bool:
    app = Seeder(_app_dsn(database))
    try:
        asyncio.run(app.as_actor(tenant_id, ("system", "i02-test"), _SEES, rows))
    except asyncpg.DivisionByZeroError:
        return False
    return True


async def _user_row(seed: Seeder, who: Person, *, status: str = "building") -> uuid.UUID:
    row = uuid.uuid4()
    await seed.run(
        "INSERT INTO daily_briefings (id, tenant_id, scope, viewer_user_id, brief_date, status, "
        "counts) VALUES ($1, $2, 'user', $3, DATE '2026-09-14', $4, $5)",
        row,
        who.tenant_id,
        who.user_id,
        status,
        json.dumps({"decision": 3, "sign_off": 6, "approval_send": 2, "overdue": 0}),
    )
    return row


def test_two_tenants_are_isolated(private_db: sc.Database) -> None:
    seed = Seeder(private_db.superuser_dsn)

    async def both() -> tuple[uuid.UUID, uuid.UUID]:
        tenants = (await seed.firm(), await seed.firm())
        for tenant in tenants:
            await _user_row(seed, await seed.person(tenant))
        return tenants

    a, b = asyncio.run(both())
    assert _app_sees(private_db, a, 1)
    assert _app_sees(private_db, b, 1)
    assert _app_sees(private_db, uuid.uuid4(), 0)


def test_rls_is_forced(private_db: sc.Database) -> None:
    forced = asyncio.run(
        Seeder(private_db.superuser_dsn).value(
            "SELECT relforcerowsecurity AND relrowsecurity FROM pg_class "
            "WHERE relname = 'daily_briefings'"
        )
    )
    assert forced is True


def test_a_ready_row_is_immutable(private_db: sc.Database) -> None:
    seed = Seeder(private_db.superuser_dsn)

    async def make() -> uuid.UUID:
        return await _user_row(seed, await seed.person(await seed.firm()))

    row = asyncio.run(make())
    asyncio.run(
        seed.run(
            "UPDATE daily_briefings SET status = 'ready', built_at = now() WHERE id = $1", row
        )
    )
    with pytest.raises(asyncpg.CheckViolationError, match="immutable"):
        asyncio.run(seed.run("UPDATE daily_briefings SET counts = '{}'::jsonb WHERE id = $1", row))


def test_an_engagement_row_needs_its_engagement_and_a_user_row_holds_no_blocks(
    private_db: sc.Database,
) -> None:
    seed = Seeder(private_db.superuser_dsn)

    async def who() -> Person:
        return await seed.person(await seed.firm())

    person = asyncio.run(who())
    with pytest.raises(asyncpg.CheckViolationError):
        asyncio.run(
            seed.run(
                "INSERT INTO daily_briefings (tenant_id, scope, viewer_user_id, brief_date) "
                "VALUES ($1, 'engagement', $2, DATE '2026-09-14')",
                person.tenant_id,
                person.user_id,
            )
        )
    with pytest.raises(asyncpg.CheckViolationError):
        asyncio.run(
            seed.run(
                "INSERT INTO daily_briefings (tenant_id, scope, viewer_user_id, brief_date, "
                "status, blocks) VALUES ($1, 'user', $2, DATE '2026-09-14', 'ready', '[]'::jsonb)",
                person.tenant_id,
                person.user_id,
            )
        )


def test_unavailable_needs_its_reason(private_db: sc.Database) -> None:
    seed = Seeder(private_db.superuser_dsn)

    async def who() -> Person:
        return await seed.person(await seed.firm())

    person = asyncio.run(who())
    with pytest.raises(asyncpg.CheckViolationError):
        asyncio.run(_user_row(seed, person, status="unavailable"))
    with pytest.raises(asyncpg.CheckViolationError):
        asyncio.run(
            seed.run(
                "INSERT INTO daily_briefings (tenant_id, scope, viewer_user_id, brief_date, "
                "status, unavailable_reason) VALUES ($1, 'user', $2, DATE '2026-09-14', "
                "'unavailable', 'because')",
                person.tenant_id,
                person.user_id,
            )
        )


def test_the_key_is_unique_per_day_and_seq(private_db: sc.Database) -> None:
    seed = Seeder(private_db.superuser_dsn)

    async def twice() -> None:
        person = await seed.person(await seed.firm())
        await _user_row(seed, person)
        await _user_row(seed, person)

    with pytest.raises(asyncpg.UniqueViolationError):
        asyncio.run(twice())


def test_no_column_holds_a_tin_or_quoted_text(private_db: sc.Database) -> None:
    rows = asyncio.run(
        Seeder(private_db.superuser_dsn).rows(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'daily_briefings'"
        )
    )
    names = {r["column_name"] for r in rows}
    for banned in ("tin", "ssn", "ein", "quote", "excerpt", "text", "body"):
        assert not any(banned in n.split("_") for n in names), banned


def test_down_then_up(private_db: sc.Database) -> None:
    seed = Seeder(private_db.superuser_dsn)
    exists = "SELECT to_regclass('public.daily_briefings') IS NOT NULL"
    migrate(private_db.owner_url, BEFORE, down=True)
    assert not asyncio.run(seed.value(exists))
    migrate(private_db.owner_url, "head")
    assert asyncio.run(seed.value(exists))
