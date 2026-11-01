"""Q-04-T054 against Postgres on PF-X1 (DEC-1530): the pack builds from the week's snapshots and
the logs, labels the test firm synthetic, and two builds from the same inputs are identical (the
row's "reproduces")."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from abacus_tools import m12_pack
from abacus_tools.quality.schema_check import Database
from abacus_tools.synthetic.scenarios.brightwater_hale import loader

from . import test_task2470_pilot_slice as pilot
from .agent_tests.support import Seeder

loaded = pilot.loaded
engines = pilot.engines
TENANT = loader.TENANT
WEEK = date(2026, 10, 26)


async def test_ac_the_pack_reproduces_from_snapshots_and_logs(loaded: Database) -> None:
    seed = Seeder(loaded.superuser_dsn)
    await loader.load(loaded.superuser_dsn, "E0", slices=("pilot",), wait=False)
    [first, *_] = [
        r["id"]
        for r in await seed.rows(
            "SELECT id FROM pilot_enrolments WHERE tenant_id = $1 ORDER BY created_at, id", TENANT
        )
    ]
    for key, value in (
        ("w4_portal_activation.v1", "0.8500"),
        ("w5_pbc_via_portal.v1", "0.5000"),
        ("w6_vs_baseline_days.v1", "-4.0000"),
        ("w7.v1.upload_review", "0.0500"),
    ):
        await seed.run(
            "INSERT INTO pilot_metric_snapshots (tenant_id, enrolment_id, metric_key, subject_id, "
            "period_start, period_end, value) VALUES ($1, $2, $3, NULL, $4, $5, $6) "
            "ON CONFLICT DO NOTHING",
            TENANT,
            first,
            key,
            WEEK,
            date(2026, 11, 1),
            Decimal(value),
        )
    args = ([TENANT], ["PF-X1"], [WEEK], ["21"], Decimal(6))
    one = await m12_pack.build(*args)
    two = await m12_pack.build(*args)
    assert one == two
    assert "(synthetic)" in one
    assert "| PF-X1 |" in one
    assert "W6 request → received vs baseline | 28.6% faster" in one  # 4 of 14 baseline days
    assert "W7 override rate · upload_review | 5.0% | 1 | green" in one
    assert "| S21 | 0 | 36.00 | no |" in one
