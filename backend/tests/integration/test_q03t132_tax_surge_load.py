"""Q-03-T132 against Postgres: the tax-surge content loads through the services (organizer import,
publish and attach; the bridge's PDF and K-1 set imports) on top of the fleet's bootstrap, and a
second run writes nothing.

Firm 1 has 12 returns (`5 + 7n mod 11`): returns 4 and 9 are 1065s with four K-1 recipients each,
the other ten are joint-shaped 1040s with an organizer and the 8879 family's two PDFs.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from abacus.kernel.db import configure_engine, configure_relay_engine, dispose_engine
from abacus_tools.quality.schema_check import Database, provisioned_database
from abacus_tools.synthetic import fleet, fleet_tax

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio


@pytest.fixture(scope="module")
def fresh(migrated_db: MigratedDatabase) -> Iterator[Database]:
    """Its own database: fleet firm 1 is the same tenant in every test that loads x1, so a
    shared database would hand Q-03-T044's test a firm already loaded."""
    with provisioned_database(roundtrip=False) as database:
        yield database
    configure_engine(migrated_db.app_url)


TAXED = fleet.FirmShape(
    seats=7, clients=3 + 15, audits=3, requests_per_audit=2, portal_people_per_audit=1
)


async def _count(seed: Seeder, sql: str, *args: object) -> int:
    return int(str(await seed.value(sql, *args)))


async def test_ac_the_tax_profile_loads_through_the_services_once(
    fresh: Database, migrated_db: MigratedDatabase
) -> None:
    await dispose_engine()
    configure_engine(fresh.app_url)
    configure_relay_engine(fresh.relay_url)
    seed = Seeder(fresh.superuser_dsn)
    [firm] = fleet.plan("x1", TAXED)
    tenant = firm.tenant
    assert fleet_tax.returns_per_firm(firm) == 12
    partnerships = [r for r in fleet_tax.returns_of(firm) if r.partnership]
    assert [r.r for r in partnerships] == [4, 9]

    first = await fleet.load(fresh.superuser_dsn, "x1", shape=TAXED)
    assert first.written > 0
    forms = {
        str(r["form"]): int(r["n"])
        for r in await seed.rows(
            "SELECT form, count(*) AS n FROM tax_returns WHERE tenant_id = $1 GROUP BY form",
            tenant,
        )
    }
    assert forms == {"1040": 10, "1065": 2}
    organizers = await _count(
        seed,
        "SELECT count(*) FROM questionnaires WHERE tenant_id = $1 AND kind = 'organizer'",
        tenant,
    )
    assert organizers == 10
    published = await _count(
        seed,
        "SELECT count(*) FROM questionnaire_template_versions WHERE tenant_id = $1 "
        "AND published_at IS NOT NULL",
        tenant,
    )
    assert published == 1
    authorizations = await _count(
        seed,
        "SELECT count(*) FROM engine_sync_events WHERE tenant_id = $1 AND kind = 'pdfs' "
        "AND summary ->> 'pdf_kind' IN ('form_8879', 'tr_579_it')",
        tenant,
    )
    assert authorizations == 10 * 2
    packages = await _count(
        seed,
        "SELECT count(*) FROM k1_packages WHERE tenant_id = $1 AND status = 'draft'",
        tenant,
    )
    assert packages == 2 * fleet_tax.RECIPIENTS
    flags = {
        str(r["flag"])
        for r in await seed.rows(
            "SELECT flag FROM feature_flag_states WHERE tenant_id = $1 AND value = 'true'", tenant
        )
    }
    assert set(fleet_tax.TAX_FLAGS) <= flags

    second = await fleet.load(fresh.superuser_dsn, "x1", shape=TAXED)
    assert second.written == 0
    assert (
        await _count(seed, "SELECT count(*) FROM tax_returns WHERE tenant_id = $1", tenant) == 12
    )
    await dispose_engine()
    configure_engine(migrated_db.app_url)
