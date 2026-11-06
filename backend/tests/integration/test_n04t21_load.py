"""N-04-T21 (TASK-3346; DEC-2335) against Postgres: the notices slice loads through the services.

"make seed-demo produces every NOT artboard's data through service APIs." It had never been loaded,
and its first run failed on the intake's source and field keys.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator

import pytest

from abacus.kernel.db import configure_engine, dispose_engine
from abacus_tools.quality.schema_check import Database, provisioned_database
from abacus_tools.synthetic.scenarios.brightwater_hale import loader
from abacus_tools.synthetic.scenarios.brightwater_hale import notices_content as nc

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase


@pytest.fixture(scope="module")
def own_db(migrated_db: MigratedDatabase) -> Iterator[Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database
    configure_engine(migrated_db.app_url)


@pytest.fixture(scope="module")
def loaded(own_db: Database, object_store: str) -> Database:
    async def load() -> None:
        await dispose_engine()
        configure_engine(own_db.app_url)
        try:
            await loader.load(own_db.superuser_dsn, "E0", slices=("notices",), wait=False)
        finally:
            await dispose_engine()

    asyncio.run(load())
    return own_db


async def test_ac_the_loaded_notices_foot_to_the_seed(loaded: Database) -> None:
    seed = Seeder(loaded.superuser_dsn)
    rows = await seed.rows(
        "SELECT status, count(*) AS n FROM notices WHERE tenant_id = $1 GROUP BY status",
        loader.TENANT,
    )
    by = {r["status"]: r["n"] for r in rows}
    assert sum(by.values()) == len(nc.NOTICES)
    for row in nc.NOTICES:
        assert by.get(row.status, 0) >= 1
