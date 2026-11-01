"""A-03-T16 part two against Postgres (TASK-2716; DEC-1767): the `sampling` slice loaded at the
2026-09-24 snapshot through the services, then loaded again with nothing written. The figures are
AUD-11 a's (the handoff and the A-03-T09 goldens), not the code's:

- BH-EBP-210 Table 2 published (moderate, 10 %, 0 %, 90 % → 25); BH FS groupings v1 published
  with 13 groupings and 14 FS lines.
- Participants: Version 1 on census v1 (409, seed 0x3C77D0, its register tie off by $182,300.00)
  and Version 2 on census v2 (412, seed 0x5E2A91, two ties), 25 items each; Ana Cruz confirms on
  Sep 15 (DEC-1767), so Version 2 is prepared by Marcus Delaney (L1) and approved by Hannah
  Leclerc (L2), its 25 the design's in draw order.

The load gets its own database: the session's `migrated_db` holds the loader test's E0."""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal

import pytest

from abacus.kernel.db import configure_engine
from abacus_tools.quality.schema_check import Database, provisioned_database
from abacus_tools.synthetic.scenarios.brightwater_hale import loader, sampling_content
from abacus_tools.synthetic.scenarios.brightwater_hale.scenario import build

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio
TENANT = loader.TENANT
SNAPSHOT = "2026-09-24"
SLICES = ("sampling",)


@pytest.fixture(scope="module")
def own_db(migrated_db: MigratedDatabase) -> Iterator[Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database
    configure_engine(migrated_db.app_url)


async def test_the_sampling_slice_loads_the_participants_sample_through_services(
    own_db: Database,
) -> None:
    configure_engine(own_db.app_url)
    seed = Seeder(own_db.superuser_dsn)
    slices = loader.expand_slices(SLICES)
    events = build(SNAPSHOT, slices=("audit_core", *slices)).events

    first = await loader.load(own_db.superuser_dsn, SNAPSHOT, slices=SLICES, wait=False)
    assert (first.replayed, first.skipped) == (len(events), 0)

    groupings = await seed.rows(
        "SELECT v.status, count(DISTINCT g.id), count(l.id) FROM grouping_set_versions v "
        "JOIN grouping_sets s ON s.id = v.grouping_set_id "
        "JOIN groupings g ON g.version_id = v.id JOIN fs_lines l ON l.grouping_id = g.id "
        "WHERE s.tenant_id = $1 AND s.key = $2 GROUP BY v.status",
        TENANT,
        sampling_content.GROUPING_SET_KEY,
    )
    assert [tuple(r) for r in groupings] == [("published", 13, 14)]

    versions = await seed.rows(
        "SELECT v.version_no, v.status, v.seed, v.final_size, p.record_count "
        "FROM sample_set_versions v JOIN sample_sets s ON s.id = v.sample_set_id "
        "JOIN sample_populations p ON p.id = v.population_id "
        "WHERE s.tenant_id = $1 AND s.title = 'Participants' ORDER BY v.version_no",
        TENANT,
    )
    statuses = [(r["version_no"], r["status"]) for r in versions]
    assert statuses[1] == (2, "approved") and statuses[0][1] in ("superseded", "draft")
    assert [(r["seed"], r["final_size"], r["record_count"]) for r in versions] == [
        (0x3C77D0, 25, 409),
        (0x5E2A91, 25, 412),
    ]
    ties = await seed.rows(
        "SELECT p.record_count, t.result, t.difference FROM completeness_ties t "
        "JOIN sample_populations p ON p.id = t.population_id WHERE p.tenant_id = $1 "
        "ORDER BY p.record_count, t.position",
        TENANT,
    )
    assert [tuple(r) for r in ties] == [
        (409, "off", Decimal("-182300.00")),
        (412, "tie", Decimal("0.00")),
        (412, "tie", Decimal("0.00")),
    ]
    rows = sampling_content.census()
    names = {r.row_key: r.name for r in rows}
    items = await seed.rows(
        "SELECT i.record_key FROM sample_items i JOIN sample_set_versions v "
        "ON v.id = i.sample_set_version_id JOIN sample_sets s ON s.id = v.sample_set_id "
        "WHERE s.tenant_id = $1 AND s.title = 'Participants' AND v.version_no = 2 "
        "ORDER BY i.position",
        TENANT,
    )
    assert [names[r["record_key"]] for r in items] == [n for n, _ in sampling_content.PARTICIPANTS]
    signed = await seed.rows(
        "SELECT level, signed_by FROM sign_offs WHERE tenant_id = $1 "
        "AND target_type = 'sample_set_version' ORDER BY level",
        TENANT,
    )
    seats = {s.initials: s for s in loader.SEATS}
    assert [(r["level"], r["signed_by"]) for r in signed] == [
        (1, loader.user_id_of(seats["MD"])),
        (2, loader.user_id_of(seats["HL"])),
    ]

    again = await loader.load(own_db.superuser_dsn, SNAPSHOT, slices=SLICES, wait=False)
    assert (again.replayed, again.skipped) == (0, len(events))
