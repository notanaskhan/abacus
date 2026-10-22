"""F-03-T29 (ADR-139, P-36) against Postgres: counts over the filters minus the tile, capped
totals, and keyset pages that walk a list with ties in the sort key without losing or repeating
a row."""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from sqlalchemy import String, column, select, values
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel import listing
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine, tenant_session

from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio

ROWS = [
    # (id, name, office, status): two offices, three statuses, ties on name.
    ("01", "Alder", "den", "open"),
    ("02", "Birch", "den", "open"),
    ("03", "Birch", "den", "in_review"),
    ("04", "Birch", "chi", "open"),
    ("05", "Cedar", "den", "issues"),
    ("06", "Cedar", "den", "issues"),
    ("07", "Dogwood", "chi", "issues"),
    ("08", "Elm", "den", "in_review"),
]

# The rows as a VALUES list: the app role creates no tables, and the queries need none.
items = (
    values(
        column("id", String),
        column("name", String),
        column("office", String),
        column("status", String),
        name="listing_probe",
    )
    .data(ROWS)
    .alias("listing_probe")
)


@pytest.fixture
async def session(migrated_db: MigratedDatabase) -> AsyncIterator[AsyncSession]:
    # An engine on this test's event loop, as the other integration tests open theirs.
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    async with tenant_session(TenantContext(uuid4(), "human", "listing-probe")) as s:
        yield s
    await dispose_engine()


async def test_counts_ignore_the_tile_filter(session: AsyncSession) -> None:
    # The list is filtered to Denver and the "issues" tile is selected.
    filters = select(items).where(items.c.office == "den")
    shown = filters.where(items.c.status == "issues")
    counts = await listing.status_counts(session, filters, items.c.status)
    assert counts == {"open": 2, "in_review": 2, "issues": 2}
    # The page itself honours the tile; the counts do not, so no tile counts itself out.
    page = (await session.execute(shown)).all()
    assert len(page) == 2
    assert counts["open"] == 2


async def test_total_is_exact_until_the_cap(session: AsyncSession) -> None:
    stmt = select(items)
    assert await listing.capped_total(session, stmt) == (8, False)
    assert await listing.capped_total(session, stmt, cap=5) == (5, True)
    assert await listing.capped_total(session, stmt, cap=8) == (8, False)


@pytest.mark.parametrize("descending", [False, True])
async def test_keyset_pages_walk_ties_without_loss_or_repeat(
    session: AsyncSession, descending: bool
) -> None:
    tenant = uuid4()
    query = listing.query_hash(sort="name", descending=descending)
    seen: list[str] = []
    cursor: str | None = None
    for _ in range(10):
        after = (
            None
            if cursor is None
            else listing.decode_cursor(cursor, tenant_id=tenant, resource="probe", query=query)
        )
        stmt = listing.keyset(
            select(items.c.id, items.c.name),
            sort=items.c.name,
            id_column=items.c.id,
            after=after,
            descending=descending,
            limit=3,
        )
        rows = (await session.execute(stmt)).all()
        page, nxt = listing.page_of(rows, limit=3, key=lambda r: r.name, id_of=lambda r: r.id)
        seen.extend(r.id for r in page)
        envelope = listing.envelope(
            [r.id for r in page],
            next_position=nxt,
            tenant_id=tenant,
            resource="probe",
            query=query,
            total=(len(ROWS), False),
        )
        cursor = envelope.next_cursor
        if cursor is None:
            break
    expected = sorted(ROWS, key=lambda r: (r[1], r[0]), reverse=descending)
    assert seen == [r[0] for r in expected]
