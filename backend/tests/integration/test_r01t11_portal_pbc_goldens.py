"""R-01-T11 (ADR-078; R-01 §5.4; DEC-348): the portal PBC slice's golden figures, read back from
a database the slice was loaded into.

The figures live in `tests/golden/scenario/brightwater_hale/portal_pbc.yaml`, typed from the
POR-03, POR-04, POR-14, AUD-03 and SHL-14 screen contracts and handoffs; none is imported from the
scenario package. Each observer reads the database and returns what it sees.

DEC-471 fills what no source names; the one figure two goldens disagree on (POR-14 a's Keystone
"4 of 9" against AUD-03's statuses) is asserted for real and marked `xfail(strict=True)` with
TASK-1221.

E0 plus `portal_pbc` loads once into this module's database; Granite Peak's SURL Draft (Thu Sep
24) postdates E0, so a second database takes the 2026-10-01 snapshot of `binders`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from datetime import date, datetime
from pathlib import Path
from typing import Final, cast

import asyncpg
import pytest
import yaml

from abacus.kernel import clock
from abacus.kernel.db import configure_engine, dispose_engine
from abacus_tools.quality.schema_check import Database, provisioned_database
from abacus_tools.synthetic.scenarios.brightwater_hale import loader

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

pytestmark = [pytest.mark.asyncio, pytest.mark.xdist_group(name="r01t11_portal_pbc_goldens")]

TENANT: Final = loader.TENANT
ZONE: Final = clock.FIRM_ZONE
GOLDEN: Final = (
    Path(__file__).resolve().parents[1] / "golden" / "scenario" / "brightwater_hale"
) / "portal_pbc.yaml"
Json = dict[str, object]

FELD: Final = "Jonah & Claire Feld"
NORTHWIND: Final = "Northwind Robotics, Inc."
GRANITE_PEAK: Final = "Granite Peak Outdoor Supply, Inc."


def _expected(case: str) -> Json:
    data = cast(Json, yaml.safe_load(GOLDEN.read_text(encoding="utf-8")))
    found = {str(c["id"]): c for c in cast(list[Json], data["cases"])}
    return cast(Json, found[case]["expected"])


def _local(at: datetime) -> str:
    return at.astimezone(ZONE).strftime("%Y-%m-%d %H:%M")


# --- observers ---------------------------------------------------------------------------------

_FELD_ITEMS = (
    "SELECT i.title, i.status FROM request_items i "
    "JOIN request_lists l ON l.id = i.request_list_id "
    "JOIN engagements e ON e.id = l.engagement_id JOIN clients c ON c.id = e.client_id "
    "WHERE i.tenant_id = $1 AND c.name = $2 AND l.kind = 'organizer' AND l.part = 1 "
    "AND i.deleted_at IS NULL"
)
_NORTHWIND_ITEMS = (
    "SELECT i.title, i.description, i.status, i.due_on, u.display_name AS assignee "
    "FROM request_items i JOIN request_lists l ON l.id = i.request_list_id "
    "JOIN engagements e ON e.id = l.engagement_id JOIN clients c ON c.id = e.client_id "
    "LEFT JOIN users u ON u.id = i.client_assignee_user_id "
    "WHERE i.tenant_id = $1 AND c.name = $2 AND l.kind = 'pbc' AND i.deleted_at IS NULL"
)


async def feld_binder(conn: asyncpg.Connection) -> Json:
    rows = await conn.fetch(_FELD_ITEMS, TENANT, FELD)
    return {
        "requests": len(rows),
        "done": sum(1 for r in rows if r["status"] == "received"),
        "open": sorted(r["title"] for r in rows if r["status"] != "received"),
    }


async def feld_inbox(conn: asyncpg.Connection) -> list[Json]:
    rows = await conn.fetch(
        "SELECT f.file_name, u.display_name, f.created_at, f.uploaded_by_staff, f.status "
        "FROM inbox_files f JOIN engagements e ON e.id = f.engagement_id "
        "JOIN clients c ON c.id = e.client_id JOIN users u ON u.id = f.uploaded_by "
        "WHERE f.tenant_id = $1 AND c.name = $2",
        TENANT,
        FELD,
    )
    items = {r["title"]: r["status"] for r in await conn.fetch(_FELD_ITEMS, TENANT, FELD)}
    return [
        {
            "file_name": r["file_name"],
            "from": r["display_name"],
            "at": _local(r["created_at"]),
            "by_staff": r["uploaded_by_staff"],
            "waiting": r["status"] == "waiting",
            "request_status": items.get("Form 1095-C From Mercer Hill Health"),
        }
        for r in rows
    ]


async def dana_titles(conn: asyncpg.Connection) -> Json:
    rows = await conn.fetch(_NORTHWIND_ITEMS, TENANT, NORTHWIND)
    dana = [r for r in rows if r["assignee"] == "Dana Kowalski"]
    w3 = next((r for r in dana if r["title"] == "W-3 for 2025"), None)
    return {
        "titles": sorted(r["title"] for r in dana),
        "w3_due": cast(date, w3["due_on"]).isoformat() if w3 is not None else None,
    }


async def aud03(conn: asyncpg.Connection) -> Json:
    rows = await conn.fetch(_NORTHWIND_ITEMS, TENANT, NORTHWIND)
    return {
        "requests": len(rows),
        "received": sum(1 for r in rows if r["status"] == "received"),
        "uploaded": sum(1 for r in rows if r["status"] == "uploaded"),
        "requested": sum(1 for r in rows if r["status"] == "requested"),
        "descriptions": [r["description"] for r in rows],
    }


async def delegated_organisations(conn: asyncpg.Connection) -> list[str]:
    rows = await conn.fetch(
        "SELECT DISTINCT k.organisation_name FROM request_delegations d "
        "JOIN contacts k ON k.tenant_id = d.tenant_id AND k.id = d.contact_id "
        "JOIN request_items i ON i.tenant_id = d.tenant_id AND i.id = d.request_item_id "
        "JOIN engagements e ON e.id = i.engagement_id JOIN clients c ON c.id = e.client_id "
        "WHERE d.tenant_id = $1 AND c.name = $2 AND d.revoked_at IS NULL",
        TENANT,
        NORTHWIND,
    )
    return sorted(str(r[0]) for r in rows)


async def keystone_room(conn: asyncpg.Connection) -> Json:
    rows = await conn.fetch(
        "SELECT i.status FROM request_delegations d "
        "JOIN contacts k ON k.tenant_id = d.tenant_id AND k.id = d.contact_id "
        "JOIN request_items i ON i.tenant_id = d.tenant_id AND i.id = d.request_item_id "
        "WHERE d.tenant_id = $1 AND k.organisation_name = 'Keystone Retirement Services' "
        "AND d.revoked_at IS NULL",
        TENANT,
    )
    return {
        "delegated": len(rows),
        "uploaded": sum(1 for r in rows if r["status"] in ("uploaded", "received")),
    }


async def surl(conn: asyncpg.Connection) -> Json | None:
    row = await conn.fetchrow(
        "SELECT i.title, i.status, i.client_visible, i.drafted_by_run_id IS NOT NULL AS drafted, "
        "i.drafted_wording_source, a.display_name AS assignee, o.display_name AS owner, "
        "i.period_start, i.period_end FROM request_items i "
        "JOIN engagements e ON e.id = i.engagement_id JOIN clients c ON c.id = e.client_id "
        "LEFT JOIN users a ON a.id = i.client_assignee_user_id "
        "LEFT JOIN users o ON o.id = i.firm_owner_user_id "
        "WHERE i.tenant_id = $1 AND c.name = $2 "
        "AND i.title = 'Support for 40 subsequent disbursements (SURL)'",
        TENANT,
        GRANITE_PEAK,
    )
    if row is None:
        return None
    return {
        "title": row["title"],
        "status": row["status"],
        "client_visible": row["client_visible"],
        "drafted": row["drafted"],
        "wording_source": row["drafted_wording_source"],
        "client_assignee": row["assignee"],
        "firm_owner": row["owner"],
        "period": [row["period_start"].isoformat(), row["period_end"].isoformat()],
    }


# --- the loaded tenants ------------------------------------------------------------------------


@pytest.fixture(scope="module")
def own_db(migrated_db: MigratedDatabase) -> Iterator[Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database
    configure_engine(migrated_db.app_url)  # hand the session's database back to later tests


@pytest.fixture(scope="module")
def surl_db(migrated_db: MigratedDatabase) -> Iterator[Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database
    configure_engine(migrated_db.app_url)


_LOADED: dict[str, loader.LoadResult] = {}


async def _load(
    db: Database, migrated_db: MigratedDatabase, at: str, slices: tuple[str, ...]
) -> loader.LoadResult:
    await dispose_engine()
    configure_engine(db.app_url)
    try:
        return await loader.load(db.superuser_dsn, at, slices=slices, wait=False)
    finally:
        await dispose_engine()
        configure_engine(migrated_db.app_url)


@pytest.fixture
async def conn(
    own_db: Database, migrated_db: MigratedDatabase
) -> AsyncIterator[asyncpg.Connection]:
    """E0 plus `portal_pbc`, loaded once (on first use) into the module's database."""
    if own_db.superuser_dsn not in _LOADED:
        _LOADED[own_db.superuser_dsn] = await _load(own_db, migrated_db, "E0", ("portal_pbc",))
    async with Seeder(own_db.superuser_dsn).held() as connection:
        yield connection


# --- goldens on the loaded tenant ---------------------------------------------------------------


async def test_feld_binder_stays_5_of_7_with_the_1095c_and_estimates_open(
    conn: asyncpg.Connection,
) -> None:
    expected = _expected("feld-binder-5-of-7")
    open_titles = sorted(cast(list[str], expected["open"]))
    assert await feld_binder(conn) == {**expected, "open": open_titles}


async def test_claires_9_12_email_waits_in_the_feld_inbox(conn: asyncpg.Connection) -> None:
    expected = _expected("feld-1095c-emailed-9-12")
    assert await feld_inbox(conn) == [
        {k: v for k, v in expected.items() if k != "request"},
    ]


async def test_danas_requests_read_the_portal_titles(conn: asyncpg.Connection) -> None:
    seen = await dana_titles(conn)
    expected = _expected("dana-client-titles")
    assert set(cast(list[str], expected["titles"])) <= set(cast(list[str], seen["titles"]))
    assert seen["w3_due"] == expected["w3_due"]


async def test_danas_census_row_reads_the_portal_title(conn: asyncpg.Connection) -> None:
    seen = await dana_titles(conn)
    assert _expected("dana-census-title")["title"] in cast(list[str], seen["titles"])


async def test_aud03_keeps_24_rows_their_totals_and_descriptions(conn: asyncpg.Connection) -> None:
    seen = await aud03(conn)
    expected = _expected("aud03-totals-kept")
    assert {k: seen[k] for k in ("requests", "received", "uploaded", "requested")} == {
        k: expected[k] for k in ("requests", "received", "uploaded", "requested")
    }
    assert set(cast(list[str], expected["descriptions"])) <= set(
        cast(list[str], seen["descriptions"])
    )


async def test_por03i_names_the_four_organisations_requests_went_to(
    conn: asyncpg.Connection,
) -> None:
    assert await delegated_organisations(conn) == _expected("dana-other-parties")["organisations"]


@pytest.mark.xfail(
    strict=True,
    reason="two goldens disagree: POR-14 a reads Keystone 4 of 9, while AUD-03's statuses "
    "(f04 goldens, 11 / 1 / 12) make 6 of Keystone's 9 done; recorded in "
    "work/tasks/TASK-1221-portal-pbc-scenario-slice.md",
)
async def test_por14a_keystone_room_reads_4_of_9(conn: asyncpg.Connection) -> None:
    assert await keystone_room(conn) == _expected("keystone-4-of-9")


async def test_a_second_load_writes_nothing(
    conn: asyncpg.Connection, own_db: Database, migrated_db: MigratedDatabase
) -> None:
    again = await _load(own_db, migrated_db, "E0", ("portal_pbc",))
    assert again.replayed == 0
    assert again.skipped == _LOADED[own_db.superuser_dsn].replayed


async def test_granite_peak_surl_is_an_owners_only_agent_draft(
    surl_db: Database, migrated_db: MigratedDatabase
) -> None:
    await _load(surl_db, migrated_db, "2026-10-01", ("binders",))
    async with Seeder(surl_db.superuser_dsn).held() as connection:
        assert await surl(connection) == _expected("granite-peak-surl-draft")


async def test_granite_peak_surl_draft_is_not_there_at_e0(conn: asyncpg.Connection) -> None:
    """SHL-14 f is Thu Sep 24: the E0 tenant has no SURL request yet."""
    assert await surl(conn) is None
