"""Q-04-T050 against Postgres on PF-X1 (DEC-1530): the W4/W5 read takes the week's snapshots of
the test firm's two shadow enrolments, means them per signal with the counts behind it, colours
them and labels the firm synthetic. Snapshots are written as Q-04-T008's job writes them."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from abacus.modules.platform.api import cross_firm, wedge_read, wedge_report
from abacus_tools.quality.schema_check import Database
from abacus_tools.synthetic.scenarios.brightwater_hale import loader

from . import test_task2470_pilot_slice as pilot
from .agent_tests.support import Seeder

loaded = pilot.loaded
engines = pilot.engines
TENANT = loader.TENANT
WEEK = date(2026, 10, 26)


async def test_ac_w4_and_w5_per_firm_with_colour_counts_owner_and_action(
    loaded: Database,
) -> None:
    seed = Seeder(loaded.superuser_dsn)
    await loader.load(loaded.superuser_dsn, "E0", slices=("pilot",), wait=False)
    enrolments = [
        r["id"]
        for r in await seed.rows(
            "SELECT id FROM pilot_enrolments WHERE tenant_id = $1 ORDER BY created_at, id", TENANT
        )
    ]
    assert len(enrolments) == 2
    for enrolment, w4, w5 in zip(
        enrolments, ("0.9000", "0.6000"), ("0.3000", "0.4000"), strict=True
    ):
        for key, value in (("w4_portal_activation.v1", w4), ("w5_pbc_via_portal.v1", w5)):
            await seed.run(
                "INSERT INTO pilot_metric_snapshots (tenant_id, enrolment_id, metric_key, "
                "subject_id, period_start, period_end, value) VALUES ($1, $2, $3, NULL, $4, $5, "
                "$6) ON CONFLICT DO NOTHING",
                TENANT,
                enrolment,
                key,
                WEEK,
                date(2026, 11, 1),
                Decimal(value),
            )
    read = await wedge_read(TENANT, WEEK)
    assert read.synthetic is True and read.weeks_live >= 4
    w4, w5 = read.signals
    assert (w4.value, w4.enrolments, w4.colour) == (Decimal("0.7500"), 2, "amber")
    assert (w5.value, w5.enrolments, w5.colour) == (Decimal("0.3500"), 2, "red")
    assert w4.owner == "AY" and w4.action and w5.action
    text = wedge_report(cross_firm([read]))
    assert "(synthetic)" in text and "75.0%" in text and "2 (90.0%, 60.0%)" in text
