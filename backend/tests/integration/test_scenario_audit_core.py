"""F-04-T20 against Postgres (F-04.10; SPEC-307 AC-1): the loaded E0 tenant shows 27 audits with
the exact type and stage splits, Northwind's PBC at 11 of 24, Granite Peak's FS PBC at 41, the
portal people's grants and `staff_can_accept_evidence` on, all as database rows; a second load
writes nothing. The figures are typed from F-04 §3.2 and blueprint 01 §9.5, not from the code.

The load gets its own database: the session's `migrated_db` already holds the loader test's E0
with Fairhaven held out, and the loader skips any event it has replayed before."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from abacus.kernel.db import configure_engine
from abacus_tools.quality.schema_check import Database, provisioned_database
from abacus_tools.synthetic.scenarios.brightwater_hale import loader
from abacus_tools.synthetic.scenarios.brightwater_hale.scenario import build

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio
TENANT = loader.TENANT


@pytest.fixture(scope="module")
def own_db(migrated_db: MigratedDatabase) -> Iterator[Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database
    configure_engine(migrated_db.app_url)  # hand the session's database back to later tests


async def _tally(seed: Seeder, sql: str) -> dict[str, int]:
    return {str(r[0]): int(r[1]) for r in await seed.rows(sql, TENANT)}


async def test_e0_shows_the_audit_core_slice_as_database_rows(own_db: Database) -> None:
    configure_engine(own_db.app_url)
    seed = Seeder(own_db.superuser_dsn)
    events = build("E0").events

    first = await loader.load(own_db.superuser_dsn, "E0", wait=False)
    assert (first.replayed, first.skipped) == (len(events), 0)

    # F-04.10: 27 = EBP 14 · FS 6 · Review 4 · Compilation/preparation 3.
    assert await _tally(
        seed,
        "SELECT CASE WHEN type IN ('compilation', 'preparation') THEN 'comp_prep' ELSE type END, "
        "count(*) FROM engagements WHERE tenant_id = $1 GROUP BY 1",
    ) == {"ebp_audit": 14, "fs_audit": 6, "review": 4, "comp_prep": 3}
    # Stages 7 / 9 / 6 / 2 / 3 on the assurance work items, in C2 codes.
    assert await _tally(
        seed,
        "SELECT phase, count(*) FROM assurance_work_items WHERE tenant_id = $1 GROUP BY 1",
    ) == {"planning": 7, "fieldwork": 9, "in_review": 6, "ready_to_release": 2, "released": 3}
    assert await _tally(
        seed, "SELECT status, count(*) FROM engagements WHERE tenant_id = $1 GROUP BY 1"
    ) == {"active": 22, "accepted": 2, "delivered": 1, "archived": 2}
    northwind = await seed.rows(
        "SELECT e.name, ce.name AS entity, count(m.*) AS team FROM engagements e "
        "JOIN client_entities ce ON ce.tenant_id = e.tenant_id AND ce.id = e.client_entity_id "
        "JOIN engagement_members m ON m.tenant_id = e.tenant_id AND m.engagement_id = e.id "
        "WHERE e.tenant_id = $1 AND e.id = $2 GROUP BY 1, 2",
        TENANT,
        loader.engagement_id_of(loader.BY_LABEL["A1"]),
    )
    assert [tuple(r) for r in northwind] == [
        ("PY2025 EBP Audit", "Northwind Robotics 401(k) Plan", 5)
    ]

    # Northwind's PBC reads 11 of 24 (DF-34); Granite Peak's FS PBC has 41 requests.
    pbc = await seed.rows(
        "SELECT l.status AS list, count(*) AS total, "
        "count(*) FILTER (WHERE i.status = 'received') AS received, "
        "count(*) FILTER (WHERE i.status = 'draft') AS drafts FROM request_lists l "
        "JOIN request_items i ON i.tenant_id = l.tenant_id AND i.request_list_id = l.id "
        "WHERE l.tenant_id = $1 GROUP BY l.id, l.status ORDER BY total",
        TENANT,
    )
    assert [tuple(r) for r in pbc] == [("published", 24, 11, 0), ("draft", 41, 0, 41)]
    assigned = await seed.value(
        "SELECT count(*) FROM request_items WHERE tenant_id = $1 "
        "AND client_assignee_user_id IS NOT NULL",
        TENANT,
    )
    assert assigned == 9 + 41  # Dana Kowalski's Northwind requests and Luis Ferrante's drafts

    # The portal people: client memberships and engagement grants, mailboxes on the sink.
    grants = await _tally(
        seed,
        "SELECT g.role, count(*) FROM client_access_grants g JOIN users u ON u.id = g.user_id "
        "WHERE g.tenant_id = $1 AND u.email LIKE '%@sink.brightwaterhale.test' GROUP BY 1",
    )
    assert grants == {"owner": 2, "tcwg": 2}

    # DEC-37: staff may accept evidence, as a row the setting reads.
    assert (
        await seed.value(
            "SELECT value FROM firm_setting_values WHERE tenant_id = $1 "
            "AND key = 'staff_can_accept_evidence'",
            TENANT,
        )
        is True
    )
    # Every replayed event left one audit row under its scenario trace.
    traces = {
        r["trace_id"]
        for r in await seed.rows(
            "SELECT trace_id FROM audit_events WHERE tenant_id = $1 AND action IN "
            "('engagement.created', 'request_list.created', 'client_access.granted', "
            "'firm_setting.set')",
            TENANT,
        )
    }
    slice_kinds = {
        "engagements.engagement_created",
        "requests.pbc_list_created",
        "identity.portal_user_added",
        "identity.firm_setting_set",
    }
    assert {loader.trace_hex(e) for e in events if e.kind in slice_kinds} <= traces

    rows = await seed.value("SELECT count(*) FROM audit_events WHERE tenant_id = $1", TENANT)
    again = await loader.load(own_db.superuser_dsn, "E0", wait=False)
    assert (again.replayed, again.skipped) == (0, len(events))
    assert await seed.value("SELECT count(*) FROM audit_events WHERE tenant_id = $1", TENANT) == (
        rows
    )
