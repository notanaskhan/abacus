"""Q-02-T13: the generated isolation test catches a real leak. On a private database, firm B's
client becomes readable under firm A (row-level security switched off on `clients`), and the
check reports it, as the generated case for `clients` would."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator

import pytest

from abacus.kernel.db import configure_engine
from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import provisioned_database

from .isolation import problems
from .support import Seeder, two_firms


@pytest.fixture(scope="module")
def private_db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


def test_a_seeded_cross_tenant_read_fails_the_isolation_check(private_db: sc.Database) -> None:
    seed = Seeder(private_db.superuser_dsn)

    async def run() -> list[str]:
        configure_engine(private_db.app_url)
        firms = await two_firms(seed)
        assert await problems(seed, "clients", firms.a_ctx, firms.b) == []
        await seed.run("ALTER TABLE clients NO FORCE ROW LEVEL SECURITY")
        await seed.run("ALTER TABLE clients DISABLE ROW LEVEL SECURITY")
        return await problems(seed, "clients", firms.a_ctx, firms.b)

    found = asyncio.run(run())
    assert "row-level security is off" in found
    assert "row-level security is not forced" in found
    assert any("of firm B's rows read under firm A" in p for p in found)
