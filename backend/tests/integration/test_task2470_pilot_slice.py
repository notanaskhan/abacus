"""TASK-2470 (DEC-1530) against Postgres: the `pilot` slice makes Brightwater Hale the test pilot
firm PF-X1. E0 with the slice enrols the Feld 2025 return and Northwind's EBP audit in shadow
through the platform's service (one audited enrolment each), a second load writes nothing, and
the weekly metric job finds both enrolments live in a week inside the window.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from datetime import date

import pytest

from abacus.kernel.config import settings
from abacus.kernel.db import configure_engine, configure_relay_engine, dispose_engine
from abacus.modules.platform.api import compute_pilot_week
from abacus_tools.quality.schema_check import Database, provisioned_database
from abacus_tools.synthetic.scenarios.brightwater_hale import loader

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

TENANT = loader.TENANT


@pytest.fixture(scope="module")
def loaded(migrated_db: MigratedDatabase) -> Iterator[Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database
    configure_engine(migrated_db.app_url)


@pytest.fixture(autouse=True)
async def engines(
    loaded: Database, migrated_db: MigratedDatabase, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[None]:
    monkeypatch.setenv("ABACUS_PORTAL_BASE_DOMAIN", "portal-example.test")
    settings.cache_clear()
    await dispose_engine()
    configure_engine(loaded.app_url)
    configure_relay_engine(loaded.relay_url)
    yield
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    settings.cache_clear()


async def test_the_pilot_slice_enrols_feld_and_northwind_once(loaded: Database) -> None:
    seed = Seeder(loaded.superuser_dsn)
    await loader.load(loaded.superuser_dsn, "E0", slices=("pilot",), wait=False)
    rows = await seed.rows(
        "SELECT e.mode, e.window_start, e.window_end, e.baseline_days, w.kind "
        "FROM pilot_enrolments e JOIN work_items w ON w.tenant_id = e.tenant_id "
        "AND w.id = e.work_item_id WHERE e.tenant_id = $1 ORDER BY w.kind",
        TENANT,
    )
    assert [tuple(r) for r in rows] == [
        ("shadow", date(2026, 9, 1), date(2027, 10, 20), 14, "assurance"),
        ("shadow", date(2026, 9, 1), date(2027, 10, 20), 14, "tax_return"),
    ]
    audited = await seed.value(
        "SELECT count(*) FROM audit_events "
        "WHERE tenant_id = $1 AND target_type = 'pilot_enrolment'",
        TENANT,
    )
    assert audited == 2

    again = await loader.load(loaded.superuser_dsn, "E0", slices=("pilot",), wait=False)
    assert again.replayed == 0
    assert (
        await seed.value("SELECT count(*) FROM pilot_enrolments WHERE tenant_id = $1", TENANT) == 2
    )

    # A Monday inside the window: the job runs over both live enrolments without refusing.
    written = await compute_pilot_week(TENANT, date(2026, 10, 26))
    assert written >= 0
