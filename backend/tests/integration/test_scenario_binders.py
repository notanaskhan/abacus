"""P-06-T08 against Postgres (P-06 §5.4; DEC-146): E0 loaded with the `binders` slice shows
1 + 48 + 0 + 40 + 152 = 241 TY2025 binders (224 returns + 17 second parts) on 224 return work
items over 214 engagements, Feld at 5 of 7 over nine categories, no TY2026 binder, and
Copperleaf's close intake at 9 requests; a second load writes nothing. The figures are typed from
BND-01, BND-02, CLS-03 and blueprint 01 §9.5, not from the code.

The load gets its own database: the session's `migrated_db` holds the loader test's E0."""

from __future__ import annotations

from collections.abc import Iterator
from uuid import UUID

import pytest

from abacus.kernel.db import configure_engine
from abacus_tools.quality.schema_check import Database, provisioned_database
from abacus_tools.synthetic.scenarios.brightwater_hale import loader
from abacus_tools.synthetic.scenarios.brightwater_hale.scenario import build

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio
TENANT = loader.TENANT
SLICES = ("binders",)


@pytest.fixture(scope="module")
def own_db(migrated_db: MigratedDatabase) -> Iterator[Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database
    configure_engine(migrated_db.app_url)  # hand the session's database back to later tests


async def _tally(seed: Seeder, sql: str) -> dict[str, int]:
    return {str(r[0]): int(r[1]) for r in await seed.rows(sql, TENANT)}


async def test_e0_with_the_binder_slice_foots_as_database_rows(own_db: Database) -> None:
    configure_engine(own_db.app_url)
    seed = Seeder(own_db.superuser_dsn)
    events = build("E0", slices=("audit_core", *SLICES)).events

    first = await loader.load(own_db.superuser_dsn, "E0", slices=SLICES, wait=False)
    assert (first.replayed, first.skipped) == (len(events), 0)

    tax = (
        "FROM request_lists l JOIN tax_returns t ON t.tenant_id = l.tenant_id "
        "AND t.work_item_id = l.work_item_id WHERE l.tenant_id = $1 AND t.tax_year = 2025"
    )
    # BND-01a: tiles 1 + 48 + 0 + 40 + 152 = 241; 224 returns + 17 second parts.
    tiles = await _tally(seed, f"SELECT l.status, count(*) {tax} GROUP BY 1")
    assert tiles == {"draft": 1, "published": 48, "complete": 40, "closed": 152}
    assert tiles.get("unpublished", 0) == 0
    assert sum(tiles.values()) == 241
    parts = await _tally(seed, f"SELECT l.part, count(*) {tax} GROUP BY 1")
    assert parts == {"1": 224, "2": 17}

    # §9.5: 224 TY2025 returns on 214 engagements (10 hold two); §9.1: 98 / 64 / 62 by office.
    returns = await seed.rows(
        "SELECT count(*) AS returns, count(DISTINCT engagement_id) AS engagements "
        "FROM tax_returns WHERE tenant_id = $1 AND tax_year = 2025",
        TENANT,
    )
    assert tuple(returns[0]) == (224, 214)
    offices = await _tally(
        seed,
        "SELECT o.name, count(*) FROM work_items w JOIN offices o ON o.id = w.office_id "
        "WHERE w.tenant_id = $1 AND w.kind = 'tax_return' GROUP BY 1",
    )
    assert offices == {"Chicago": 98, "Denver": 64, "New York": 62}
    # BND-01d: no TY2026 binder.
    ty2026 = await seed.value(
        "SELECT count(*) FROM request_lists l JOIN tax_returns t ON t.tenant_id = l.tenant_id "
        "AND t.work_item_id = l.work_item_id WHERE l.tenant_id = $1 AND t.tax_year = 2026",
        TENANT,
    )
    assert ty2026 == 0

    # BND-02a: the Feld 2025 Binder, Published, 5 of 7 over nine categories, 2 open.
    feld = await seed.rows(
        "SELECT l.status, l.name, count(DISTINCT c.id) AS categories, "
        "count(DISTINCT i.id) AS requests, "
        "count(DISTINCT i.id) FILTER (WHERE i.status = 'received') AS received, a.open_count "
        "FROM request_lists l JOIN work_items w ON w.id = l.work_item_id "
        "JOIN request_categories c ON c.request_list_id = l.id "
        "JOIN request_items i ON i.request_list_id = l.id "
        "JOIN binder_activity a ON a.binder_id = l.id "
        "WHERE l.tenant_id = $1 AND w.engagement_id = $2 GROUP BY l.id, a.open_count",
        TENANT,
        UUID(loader.ENGAGEMENT_BY_LABEL["jonah-and-claire-feld"].id),
    )
    assert [tuple(r) for r in feld] == [("published", "2025 Binder", 9, 7, 5, 2)]

    # BND-01: "Marked done by Owen Calder · Jun 1" names a person.
    marked = await seed.value(
        "SELECT u.display_name FROM request_lists l JOIN users u ON u.id = l.marked_done_by "
        "JOIN engagements e ON e.id = l.engagement_id JOIN clients c ON c.id = e.client_id "
        "WHERE l.tenant_id = $1 AND c.name = 'Ridgeline Property Partners, LP' AND l.part = 1",
        TENANT,
    )
    assert marked == "Owen Calder"

    # SHL-14d / CLS-03: Copperleaf's close intake, 8 recurring + 1 ad hoc, 7 received.
    intake = await seed.rows(
        "SELECT count(*) AS requests, count(*) FILTER (WHERE i.status = 'received') AS received, "
        "count(*) FILTER (WHERE i.incorporation_state = 'pending_incorporation') AS pending "
        "FROM request_lists l JOIN request_items i ON i.request_list_id = l.id "
        "WHERE l.tenant_id = $1 AND l.kind = 'close_intake'",
        TENANT,
    )
    assert tuple(intake[0]) == (9, 7, 1)

    rows = await seed.value("SELECT count(*) FROM audit_events WHERE tenant_id = $1", TENANT)
    again = await loader.load(own_db.superuser_dsn, "E0", slices=SLICES, wait=False)
    assert (again.replayed, again.skipped) == (0, len(events))
    assert await seed.value("SELECT count(*) FROM audit_events WHERE tenant_id = $1", TENANT) == (
        rows
    )
