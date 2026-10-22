"""F-04-T13 against Postgres (F-04.15): E0 loads through the loader with a scenario trace on
every event's audit row and the firm's clock in offset mode at the demo instant; a second run
writes nothing; a held-out client is absent."""

from __future__ import annotations

import pytest

from abacus.kernel.db import configure_engine
from abacus_tools.synthetic.scenarios.brightwater_hale import loader
from abacus_tools.synthetic.scenarios.brightwater_hale.epochs import DEMO_INSTANT
from abacus_tools.synthetic.scenarios.brightwater_hale.holdouts import HOLDOUTS
from abacus_tools.synthetic.scenarios.brightwater_hale.scenario import build

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio


async def _count(seed: Seeder, sql: str, *args: object) -> int:
    return int(str(await seed.value(sql, *args)))


async def test_e0_loads_once_with_scenario_traces_and_an_offset_clock(
    migrated_db: MigratedDatabase,
) -> None:
    configure_engine(migrated_db.app_url)
    seed = Seeder(migrated_db.superuser_dsn)
    holdout = next(iter(HOLDOUTS))
    events = build("E0", (holdout,)).events

    first = await loader.load(migrated_db.superuser_dsn, "E0", (holdout,), wait=False)
    assert (first.replayed, first.skipped) == (len(events), 0)
    traces = {
        r["trace_id"]
        for r in await seed.rows(
            "SELECT DISTINCT trace_id FROM audit_events WHERE tenant_id = $1", loader.TENANT
        )
    }
    assert {loader.trace_hex(e) for e in events} <= traces
    audits = await _count(
        seed, "SELECT count(*) FROM audit_events WHERE tenant_id = $1", loader.TENANT
    )
    clients = await _count(
        seed, "SELECT count(*) FROM clients WHERE tenant_id = $1", loader.TENANT
    )
    assert clients == len(build("E0", (holdout,)).clients)
    assert (
        await seed.value("SELECT synthetic FROM firms WHERE tenant_id = $1", loader.TENANT) is True
    )
    clock = await seed.rows(
        "SELECT mode, anchor_at FROM firm_demo_clocks WHERE tenant_id = $1", loader.TENANT
    )
    assert (clock[0]["mode"], clock[0]["anchor_at"]) == ("offset", DEMO_INSTANT)

    again = await loader.load(migrated_db.superuser_dsn, "E0", (holdout,), wait=False)
    assert (again.replayed, again.skipped) == (0, len(events))
    assert audits == await _count(
        seed, "SELECT count(*) FROM audit_events WHERE tenant_id = $1", loader.TENANT
    )
