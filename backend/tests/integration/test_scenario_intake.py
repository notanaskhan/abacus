"""P-07-T50 against Postgres (TASK-1444; DEC-593): the `intake` slice loaded with the
`thornbury_estate` holdout at the 2026-09-24 snapshot, through the services, then loaded again with
nothing written; and the synthetic CCH client list scored against the loaded firm as Grace Holloway
would see it in CLI-06 g: 204 matched, 8 to review, 0 new (DEC-441's dedupe, in Postgres).

- CLI-06 a, h: Walter Thornbury is a client without his estate; Samuel Ito's "Harborline Trust
  Company" check over him has an open hit.
- ENG-03 a, d: the Fairhaven "PY2025 EBP Audit" and Granite Peak "FY2026 Financial Statement Audit"
  drafts at step 1.
- CLI-07 f: Meridian's FY2026 continuance answered, Low, one Low flag, sent to the partner.

Staging is not exercised here (no hosted database is reachable from a builder's session).
The load gets its own database: the session's `migrated_db` holds the loader test's E0."""

from __future__ import annotations

import csv
from collections.abc import Iterator
from uuid import UUID

import pytest

from abacus.kernel.clock import system_now
from abacus.kernel.db import TenantContext, configure_engine
from abacus.modules.identity.api import AuthContext
from abacus.modules.organisations.api import dedupe_candidates
from abacus_tools.quality.schema_check import Database, provisioned_database
from abacus_tools.synthetic.scenarios.brightwater_hale import client_list, loader
from abacus_tools.synthetic.scenarios.brightwater_hale.scenario import build

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio
TENANT = loader.TENANT
SNAPSHOT = "2026-09-24"
SLICES = ("intake",)
HOLDOUTS = ("thornbury_estate",)
SEATS = {s.initials: s for s in loader.SEATS}


def user(initials: str) -> UUID:
    return loader.user_id_of(SEATS[initials])


def grace() -> AuthContext:
    who = user("GH")
    return AuthContext(
        TenantContext(TENANT, "human", str(who)), who, UUID(int=0), "firm_admin", system_now()
    )


@pytest.fixture(scope="module")
def own_db(migrated_db: MigratedDatabase) -> Iterator[Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database
    configure_engine(migrated_db.app_url)  # hand the session's database back to later tests


async def test_the_intake_slice_loads_and_the_cch_file_scores_204_8_0(own_db: Database) -> None:
    configure_engine(own_db.app_url)
    seed = Seeder(own_db.superuser_dsn)
    slices = loader.expand_slices(SLICES)
    events = build(SNAPSHOT, HOLDOUTS, ("audit_core", *slices)).events

    first = await loader.load(own_db.superuser_dsn, SNAPSHOT, HOLDOUTS, slices=SLICES, wait=False)
    assert (first.replayed, first.skipped) == (len(events), 0)

    # CLI-06 a: Walter Thornbury, without his estate.
    entities = await seed.rows(
        "SELECT e.name FROM client_entities e JOIN clients c ON c.id = e.client_id "
        "WHERE c.tenant_id = $1 AND c.name = 'Walter Thornbury'",
        TENANT,
    )
    assert [r[0] for r in entities] == ["Walter Thornbury"]
    assert not await seed.rows(
        "SELECT 1 FROM client_entities WHERE tenant_id = $1 "
        "AND name = 'Estate of Walter Thornbury'",
        TENANT,
    )

    # CLI-06 h: the Harborline hit over Walter Thornbury, open (no assessment).
    hits = await seed.rows(
        "SELECT r.id, (SELECT count(*) FROM conflict_result_events e WHERE e.result_id = r.id) "
        "FROM conflict_results r JOIN conflict_checks c ON c.id = r.check_id "
        "JOIN clients cl ON cl.id = c.subject_id WHERE c.tenant_id = $1 "
        "AND cl.name = 'Walter Thornbury' AND c.run_by = $2 AND c.status = 'hits'",
        TENANT,
        user("SI"),
    )
    assert hits and all(r[1] == 0 for r in hits)

    # ENG-03 a, d: the two drafts, Margaret Okonkwo's (DEC-593), at step 1.
    drafts = await seed.rows(
        "SELECT payload->>'name', type_code, step FROM engagement_drafts WHERE tenant_id = $1 "
        "AND created_by = $2 AND discarded_at IS NULL ORDER BY 1",
        TENANT,
        user("MO"),
    )
    assert {tuple(r) for r in drafts} >= {
        ("FY2026 Financial Statement Audit", "fs_audit", "client_type"),
        ("PY2025 EBP Audit", "ebp_audit", "client_type"),
    }

    # CLI-07 f: Meridian's continuance, Low, one Low flag, with the partner.
    meridian = await seed.rows(
        "SELECT r.id, r.kind, r.status, r.risk_rating FROM acceptance_records r "
        "JOIN engagements e ON e.id = r.engagement_id WHERE r.tenant_id = $1 "
        "AND e.name = 'FY2026 FS Audit'",
        TENANT,
    )
    assert [tuple(r)[1:] for r in meridian] == [("continuance", "awaiting_partner", "low")]
    flags = await seed.rows(
        "SELECT severity, authored_by FROM acceptance_flags WHERE tenant_id = $1 "
        "AND record_id = $2",
        TENANT,
        meridian[0]["id"],
    )
    assert [tuple(r) for r in flags] == [("low", user("HL"))]  # the title is sealed

    # CLI-06 g: the CCH export, scored as Grace sees it.
    with client_list.FILE.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 212
    matched = review = new = 0
    expected = {r.client_id: r for r in client_list.rows()}
    for row in rows:
        found = await dedupe_candidates(grace(), row["Client Name"])
        if not found:
            new += 1
            continue
        best = found[0]
        assert best.display_name == expected[row["Client ID"]].expected, row["Client Name"]
        if best.score >= client_list.MATCH_AT:
            matched += 1
        else:
            review += 1
    assert (matched, review, new) == (204, 8, 0)

    second = await loader.load(own_db.superuser_dsn, SNAPSHOT, HOLDOUTS, slices=SLICES, wait=False)
    assert (second.replayed, second.skipped) == (0, len(events))
