"""A-03-T16 part two against Postgres (TASK-2716; DEC-1767): the `sampling` slice loaded at the
2026-09-24 snapshot through the services, then loaded again with nothing written. The figures are
AUD-11 a's (the handoff and the A-03-T09 goldens), not the code's:

- BH-EBP-210 Table 2 published (moderate, 10 %, 0 %, 90 % → 25); BH FS groupings v1 published
  with 13 groupings and 14 FS lines.
- Participants: Version 1 on census v1 (409, seed 0x3C77D0, its register tie off by $182,300.00)
  and Version 2 on census v2 (412, seed 0x5E2A91, two ties), 25 items each; Ana Cruz confirms on
  Sep 15 (DEC-1767), so Version 2 is prepared by Marcus Delaney (L1) and approved by Hannah
  Leclerc (L2), its 25 the design's in draw order.
- Granite Peak FY2026 (TASK-2717; DEC-1768): the 128-account NetSuite TB (71,910,000 each side)
  adopted and mapped on BH FS groupings v1 with the predecessor's FY2025 mapping (122 keys,
  DEC-1769), confirmed by Caleb Dunn (L1) once G2 is met; the
  subsequent-period GL's disbursements, 1,912 payments, $38,640,200.00, tie to the operating
  account with no gap in check numbers; "Disbursements" Version 1 (seed 0x7C31B4, draft) is
  24 + 16 = 40 items, $3,698,700.00, the SURL payments in draw order. The load runs to
  AUD-11 f's clock (Sep 24, 10:20 AM).

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
NORTHWIND = loader.engagement_id_of(loader.BY_LABEL["A1"])
GRANITE = loader.engagement_id_of(loader.BY_LABEL["A2"])
SNAPSHOT = "2026-09-24T10:20"
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
        "JOIN sample_populations p ON p.id = t.population_id WHERE p.engagement_id = $1 "
        "ORDER BY p.record_count, t.position",
        NORTHWIND,
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

    tb = await seed.rows(
        "SELECT s.line_count, s.total_debit, s.total_credit FROM ledger_snapshots s "
        "JOIN trial_balance_versions v ON v.snapshot_id = s.id "
        "JOIN trial_balances t ON t.id = v.trial_balance_id "
        "WHERE t.engagement_id = $1",
        GRANITE,
    )
    assert [tuple(r) for r in tb] == [(128, Decimal("71910000.00"), Decimal("71910000.00"))]
    mapping = await seed.rows(
        "SELECT o.level, o.signed_by FROM sign_offs o JOIN mapping_sets m ON m.id = o.target_id "
        "WHERE m.engagement_id = $1 AND o.target_type = 'mapping_set'",
        GRANITE,
    )
    assert [tuple(r) for r in mapping] == [(1, loader.user_id_of(seats["CD"]))]
    prior = await seed.rows(
        "SELECT m.prior_source, i.title, "
        "(SELECT count(*) FROM jsonb_object_keys(m.predecessor_keys)) AS keys "
        "FROM mapping_sets m JOIN evidence_versions v "
        "ON v.id = m.predecessor_evidence_version_id JOIN evidence_items i "
        "ON i.id = v.evidence_item_id WHERE m.engagement_id = $1",
        GRANITE,
    )
    assert [tuple(r) for r in prior] == [
        ("predecessor_file", sampling_content.PREDECESSOR_FILE, 122)
    ]
    gl = await seed.rows(
        "SELECT p.record_count, p.amount_total, t.result, t.difference "
        "FROM sample_populations p JOIN completeness_ties t ON t.population_id = p.id "
        "WHERE p.engagement_id = $1 AND p.source_kind = 'general_ledger' ORDER BY t.position",
        GRANITE,
    )
    assert [tuple(r) for r in gl] == [
        (1912, Decimal("38640200.00"), "tie", Decimal("0.00")),
        (1912, Decimal("38640200.00"), "tie", None),
    ]
    drawn = await seed.rows(
        "SELECT v.version_no, v.status, v.seed, v.final_size, r.amount FROM sample_sets s "
        "JOIN sample_set_versions v ON v.sample_set_id = s.id "
        "JOIN sample_items i ON i.sample_set_version_id = v.id "
        "JOIN sample_population_records r ON r.population_id = v.population_id "
        "AND r.record_key = i.record_key "
        "WHERE s.title = 'Disbursements' AND s.tenant_id = $1 ORDER BY i.position",
        TENANT,
    )
    assert {(r["version_no"], r["status"], r["seed"], r["final_size"]) for r in drawn} == {
        (1, "draft", 0x7C31B4, 40)
    }
    assert [r["amount"] for r in drawn] == [Decimal(a) for *_, a in sampling_content.SURL]

    again = await loader.load(own_db.superuser_dsn, SNAPSHOT, slices=SLICES, wait=False)
    assert (again.replayed, again.skipped) == (0, len(events))
