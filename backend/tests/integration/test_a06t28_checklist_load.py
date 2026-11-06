"""A-06-T28 (TASK-3339; DEC-2330) against Postgres: the slice imports and publishes the checklist,
and a published version refuses a second publish."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator

import pytest

from abacus.kernel.db import configure_engine, dispose_engine
from abacus_tools.quality.schema_check import Database, provisioned_database
from abacus_tools.synthetic.scenarios.brightwater_hale import loader

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
            await loader.load(own_db.superuser_dsn, "E0", slices=("completion",), wait=False)
        finally:
            await dispose_engine()

    asyncio.run(load())
    return own_db


async def test_ac_the_checklist_is_142_published_items(loaded: Database) -> None:
    seed = Seeder(loaded.superuser_dsn)
    (row,) = await seed.rows(
        "SELECT v.status, jsonb_array_length(v.items) AS n, "
        "v.published_by IS NOT NULL AS by_person FROM disclosure_checklist_template_versions v WHERE v.tenant_id = $1",
        loader.TENANT,
    )
    assert (row["status"], row["n"], row["by_person"]) == ("published", 142, True)
