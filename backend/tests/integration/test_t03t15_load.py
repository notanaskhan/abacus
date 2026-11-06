"""T-03-T15 (TASK-3337; DEC-2328) against Postgres: the slice loads through the services."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator

import pytest

from abacus.kernel.db import configure_engine, dispose_engine
from abacus_tools.quality.schema_check import Database, provisioned_database
from abacus_tools.synthetic.scenarios.brightwater_hale import loader
from abacus_tools.synthetic.scenarios.brightwater_hale.loader import TENANT

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
            await loader.load(own_db.superuser_dsn, "E0", slices=("tax_schedules",), wait=False)
        finally:
            await dispose_engine()

    asyncio.run(load())
    return own_db


async def test_ac_the_loaded_tenant_foots_to_tax_13(loaded: Database) -> None:
    seed = Seeder(loaded.superuser_dsn)
    rows = await seed.rows(
        "SELECT status, count(DISTINCT tax_return_id) AS n FROM filing_extensions "
        "WHERE tenant_id = $1 GROUP BY status",
        TENANT,
    )
    by = {r["status"]: r["n"] for r in rows}
    assert by["filed"] == 82
    assert by["prepared"] == 79
    assert by["not_filed"] == 1
    assert (
        await seed.value("SELECT count(*) FROM estimate_schedules WHERE tenant_id = $1", TENANT)
        == 7
    )


async def test_ac_the_organizer_is_v6_owned_and_feld_answered_eight(loaded: Database) -> None:
    seed = Seeder(loaded.superuser_dsn)
    assert (
        await seed.value(
            "SELECT v.version FROM questionnaire_template_versions v "
            "JOIN questionnaire_templates t ON t.id = v.template_id "
            "WHERE t.tenant_id = $1 AND t.key = $2 AND v.published_at IS NOT NULL",
            TENANT,
            "organizer_1040",
        )
        == 6
    )
    assert (
        await seed.value(
            "SELECT count(DISTINCT a.question_id) FROM answer_versions a "
            "JOIN questions q ON q.id = a.question_id "
            "JOIN questionnaires n ON n.id = q.questionnaire_id "
            "WHERE n.tenant_id = $1 AND n.source_template_version_id IS NOT NULL",
            TENANT,
        )
        == 8
    )
