"""P-10-T05 (TASK-5114; P-10 §4.2; ADR-232; SPEC-647): migration 0683 `realtime_events`.

Row acceptance: "up/down/up passes, RLS is forced, and the prune removes rows older than 24 h under
the demo clock."
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from uuid import UUID

import asyncpg
import pytest

from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import migrate, provisioned_database

from .agent_tests.support import Seeder

PRUNE = "SELECT prune_realtime_events(100)"
SYSTEM = ("system", "notifications.realtime_prune")


@pytest.fixture(scope="module")
def private_db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


async def _firm_with_events(seeder: Seeder) -> UUID:
    tenant = await seeder.firm()
    for hours in (25, 1):
        await seeder.run(
            "INSERT INTO realtime_events (tenant_id, topic, type, at) "
            "VALUES ($1, 'engagement:x', 'invalidate', now() - make_interval(hours => $2))",
            tenant,
            hours,
        )
    return tenant


def test_rls_is_forced(private_db: sc.Database) -> None:
    forced = asyncio.run(
        Seeder(private_db.superuser_dsn).value(
            "SELECT relforcerowsecurity AND relrowsecurity FROM pg_class "
            "WHERE relname = 'realtime_events'"
        )
    )
    assert forced is True


def test_the_prune_removes_rows_past_24_hours(private_db: sc.Database) -> None:
    seeder = Seeder(private_db.superuser_dsn)
    tenant = asyncio.run(_firm_with_events(seeder))
    asyncio.run(seeder.as_actor(tenant, SYSTEM, PRUNE))
    left = asyncio.run(
        seeder.value("SELECT count(*) FROM realtime_events WHERE tenant_id = $1", tenant)
    )
    assert left == 1


def test_only_the_prune_actor_prunes(private_db: sc.Database) -> None:
    seeder = Seeder(private_db.superuser_dsn)
    tenant = asyncio.run(_firm_with_events(seeder))
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        asyncio.run(seeder.as_actor(tenant, ("human", str(tenant)), PRUNE))


def test_channels_are_sharded_and_stable(private_db: sc.Database) -> None:
    seeder = Seeder(private_db.superuser_dsn)
    channel = asyncio.run(
        seeder.value("SELECT realtime_channel('00000000-0000-0000-0000-000000000001')")
    )
    assert isinstance(channel, str)
    assert channel.startswith("realtime_")
    assert 0 <= int(channel.removeprefix("realtime_")) < 16


def test_down_then_up(private_db: sc.Database) -> None:
    seeder = Seeder(private_db.superuser_dsn)
    migrate(private_db.owner_url, "0682", down=True)
    assert not asyncio.run(
        seeder.value("SELECT to_regclass('public.realtime_events') IS NOT NULL")
    )
    migrate(private_db.owner_url, "head")
    assert asyncio.run(seeder.value("SELECT to_regclass('public.realtime_events') IS NOT NULL"))
