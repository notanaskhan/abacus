"""T-03-T15 (TASK-3337; DEC-2371) against Postgres: the slice loads through the services."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import date

import pytest

from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.modules.requests.api import request_item_state
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


async def test_ac_tax_13_b_estimates_and_their_confirmations(
    loaded: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DF-34 (TASK-3397): Q3 as TAX-13 b draws it, the confirmations sent to the client's own
    person through the service and confirmed by that person's upload on the designed day."""
    seed = Seeder(loaded.superuser_dsn)
    rows = await seed.rows(
        "SELECT c.name AS client, i.status, i.paid_on, i.scheduled_for, "
        "i.confirmation_request_item_id AS item FROM estimate_installments i "
        "JOIN estimate_schedules s ON s.id = i.schedule_id "
        "JOIN client_entities e ON e.id = s.client_entity_id "
        "JOIN clients c ON c.id = e.client_id "
        "WHERE s.tenant_id = $1 AND i.quarter = 3",
        TENANT,
    )
    by = {r["client"]: r for r in rows}
    assert {c: r["status"] for c, r in by.items()} == {
        "Jonah & Claire Feld": "scheduled",
        "Meera Shah": "confirmation_requested",
        "Calloway Family Trust": "paid",
        "Elena Varga": "paid",
        "Gloria Mendez": "not_confirmed",
        "Marcus & Dana Whitley": "not_required",
        "Estate of Walter Thornbury": "not_required",
    }
    assert by["Elena Varga"]["paid_on"] == date(2026, 9, 9)
    assert by["Calloway Family Trust"]["paid_on"] == date(2026, 9, 14)
    assert by["Jonah & Claire Feld"]["scheduled_for"] == date(2026, 9, 15)
    # Names come through the identity engine: this database's.
    monkeypatch.setenv("ABACUS_IDENTITY_DATABASE_URL", loaded.identity_url)
    settings.cache_clear()
    await dispose_engine()
    configure_engine(loaded.app_url)
    system = TenantContext(TENANT, "system", "test")
    seen = {}
    for client in ("Jonah & Claire Feld", "Meera Shah", "Calloway Family Trust", "Elena Varga"):
        state = await request_item_state(system, by[client]["item"])
        assert state is not None
        seen[client] = (state.confirmed, state.contact_name, state.confirmed_on)
    await dispose_engine()
    settings.cache_clear()
    assert seen == {
        "Jonah & Claire Feld": (True, "Claire Feld", date(2026, 9, 11)),
        "Meera Shah": (False, "Meera Shah", None),
        "Calloway Family Trust": (True, "Eleanor Calloway", date(2026, 9, 14)),
        "Elena Varga": (True, "Elena Varga", date(2026, 9, 9)),
    }


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
