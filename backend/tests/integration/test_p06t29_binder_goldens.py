# ac-test-author: ayushkbhatia
"""P-06-T29 (ADR-078): golden figures for the Brightwater Hale binder slice (P-06-T08, SPEC-319
AC-10), checked on the loaded tenant.

Every expected figure is a literal typed from P-06 §5.4, the BND-01 handoff ROWS 1 to 15 and the
BND-01, BND-02, SHL-14 and SHL-20 screen contracts. None is imported from the scenario package:
reading the slice's own constants would make the check circular. Each figure family is an
observer that reads the database (or, for BND-01 a, b and d, the public `GET /v1/binders` route
as Grace Holloway) and returns what it sees. A second set of tests changes one row per family
inside a transaction that is rolled back and proves the observer then reports a different
figure, so the suite fails under a seeded change to any §5.4 figure.

Figures the seed does not carry yet are asserted for real and marked `xfail(strict=True)` with
the task file that records them:
- Granite Peak's SURL Draft loads from the 2026-10-01 snapshot (SHL-14 f is Thu Sep 24; its
  fields are checked in `test_r01t11_portal_pbc_goldens.py`); its 31 files, of which SHL-20 names
  two, and the later SHL-20 states are not seeded, and Claire's two BND-02 g files wait for
  scenario documents.
- Thornbury's "6 of 15 · 3 overdue" and the other named rows' "n of m" stay declared data:
  DEC-146 writes requests only for Feld and the close intake, and no source lists the rest.

Decided drift, asserted as decided: Osterberg's binder is Published in the database; BND-01 c's
"Unpublished Sep 2 by Remy Vidal" is that artboard's fixture override, because BND-01 a reads
0 Unpublished at the same instant (DEC-146).

The load gets its own database, like the P-06-T08 scenario test."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from datetime import UTC, date, datetime
from typing import Final, cast

import asyncpg
import httpx
import pytest

from abacus.api import create_app
from abacus.kernel import clock
from abacus.kernel.config import settings
from abacus.kernel.db import configure_engine, dispose_engine
from abacus.kernel.flags import forget_flags
from abacus.modules.identity.api import configure_verifier, reset_verifier
from abacus_tools.fakes.identity import FakeIdentityProvider
from abacus_tools.quality.schema_check import Database, provisioned_database
from abacus_tools.synthetic.scenarios.brightwater_hale import loader

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio

TENANT: Final = loader.TENANT
E0: Final = datetime(2026, 9, 14, 14, 24, tzinfo=UTC)  # Mon Sep 14, 2026, 9:24 AM Central
ZONE: Final = clock.FIRM_ZONE

Figures = dict[str, object]
Observer = Callable[[asyncpg.Connection], Awaitable[Figures]]

# --- expected figures (P-06 §5.4; BND-01 spec ROWS 1-15; screen contracts) ---------------------

TILES: Final = {"draft": 1, "published": 48, "unpublished": 0, "complete": 40, "closed": 152}
PARTS: Final = {"2025 Binder": 224, "2025 Binder pt 2": 17}
# BND-01 ROWS 1-15: (client, part) -> (work item, status, last client activity in Central time).
ROWS: Final[dict[tuple[str, int], tuple[str, str, str | None]]] = {
    ("Jonah & Claire Feld", 1): ("2025 Form 1040", "published", "2026-09-14 09:12"),
    ("Ridgeline Property Partners, LP", 1): ("2025 Form 1065", "complete", "2026-06-01"),
    ("Ridgeline Property Partners, LP", 2): ("2025 Form 1065", "published", "2026-09-11"),
    ("Meera Shah", 1): ("2025 Form 1040", "published", "2026-09-09"),
    ("Calloway Family Trust", 1): ("2025 Form 1041", "complete", "2026-09-09"),
    ("Harborview Dental Properties, LP", 1): ("2025 Form 1065", "complete", "2026-08-28"),
    ("Elena Varga", 1): ("2025 Form 1040", "complete", "2026-08-30"),
    ("Estate of Walter Thornbury", 1): ("2025 Form 1040", "published", "2026-09-09"),
    ("Gloria Mendez", 1): ("2025 Form 1040", "published", "2026-09-13"),  # "Yesterday"
    ("Morgan & Kai Ferris", 1): ("2025 Form 1040", "published", "2026-09-09"),
    ("Rafael Quintero", 1): ("2025 Form 1040", "draft", None),  # "—"
    ("Lakeshore Literacy Alliance", 1): (
        "2025 Form 990 (FYE Jun 30, 2026)",
        "published",
        "2026-09-10",
    ),
    ("Fenwick Family Foundation", 1): ("2025 Form 990-PF", "published", "2026-08-11"),
    ("Marcus & Dana Whitley", 1): ("2025 Form 1040", "closed", "2026-04-02"),
    ("Copperleaf Coffee Roasters, Inc.", 1): ("2025 Form 1120-S", "closed", "2026-03-06"),
    # BND-01 c's binder: Published in the database (DEC-146), no client activity.
    ("Benjamin Osterberg", 1): ("2025 Form 1040", "published", None),
}
# "Marked done by {person} · {date}" and "Return accepted Apr 10".
MARKED_DONE: Final = {
    "Ridgeline Property Partners, LP": ("Owen Calder", "2026-06-01"),
    "Calloway Family Trust": ("Eleanor Calloway", "2026-09-09"),
    "Harborview Dental Properties, LP": ("Dr. Sofia Lindqvist", "2026-08-28"),
    "Elena Varga": ("Elena Varga", "2026-08-30"),
}
WHITLEY_CLOSED: Final = "2026-04-10"
# BND-01 ROWS "n of m".
PROGRESS: Final[dict[tuple[str, int], tuple[int, int]]] = {
    ("Jonah & Claire Feld", 1): (5, 7),
    ("Ridgeline Property Partners, LP", 1): (21, 21),
    ("Ridgeline Property Partners, LP", 2): (1, 3),
    ("Meera Shah", 1): (15, 17),
    ("Calloway Family Trust", 1): (9, 9),
    ("Harborview Dental Properties, LP", 1): (18, 18),
    ("Elena Varga", 1): (8, 8),
    ("Estate of Walter Thornbury", 1): (6, 15),
    ("Gloria Mendez", 1): (4, 11),
    ("Morgan & Kai Ferris", 1): (2, 12),
    ("Rafael Quintero", 1): (0, 10),
    ("Lakeshore Literacy Alliance", 1): (7, 16),
    ("Fenwick Family Foundation", 1): (5, 14),
    ("Marcus & Dana Whitley", 1): (14, 14),
    ("Copperleaf Coffee Roasters, Inc.", 1): (12, 12),
}
FELD_CATEGORIES: Final = [  # BND-02 a, in portal order
    "Personal & Household Information",
    "Income Sources",
    "Home & Property",
    "Health & Medical",
    "Education & Student",
    "Retirement",
    "Charitable & Donations",
    "Business & Self-Employment",
    "Other Activity",
]
KEYSTONE: Final = "Bridge letter — Keystone, Oct–Dec 2025"  # noqa: RUF001 (verbatim)
SQUARE: Final = "Square payouts — August"

# --- observers ---------------------------------------------------------------------------------

_TAX = (
    "FROM request_lists l JOIN tax_returns t ON t.tenant_id = l.tenant_id "
    "AND t.work_item_id = l.work_item_id WHERE l.tenant_id = $1 AND t.tax_year = $2"
)
_NAMED = (
    "SELECT c.name AS client, l.part, l.status, w.name AS work_item, a.last_client_activity_at, "
    "l.marked_done_at, d.display_name AS marked_done_by, l.closed_at "
    "FROM request_lists l JOIN tax_returns t ON t.tenant_id = l.tenant_id "
    "AND t.work_item_id = l.work_item_id AND t.tax_year = 2025 "
    "JOIN work_items w ON w.id = l.work_item_id JOIN engagements e ON e.id = l.engagement_id "
    "JOIN clients c ON c.id = e.client_id "
    "LEFT JOIN binder_activity a ON a.tenant_id = l.tenant_id AND a.binder_id = l.id "
    "LEFT JOIN users d ON d.id = l.marked_done_by "
    "WHERE l.tenant_id = $1 AND c.name = ANY($2::text[])"
)


def _local(at: datetime | None, *, minutes: bool = False) -> str | None:
    if at is None:
        return None
    return at.astimezone(ZONE).strftime("%Y-%m-%d %H:%M" if minutes else "%Y-%m-%d")


async def tiles(conn: asyncpg.Connection) -> Figures:
    rows = await conn.fetch(f"SELECT l.status, count(*) {_TAX} GROUP BY 1", TENANT, 2025)
    seen = {s: 0 for s in TILES} | {str(r[0]): int(r[1]) for r in rows}
    return {"tiles": seen, "total": sum(seen.values())}


async def parts(conn: asyncpg.Connection) -> Figures:
    rows = await conn.fetch(f"SELECT l.name, count(*) {_TAX} GROUP BY 1", TENANT, 2025)
    return {"parts": {str(r[0]): int(r[1]) for r in rows}}


async def ty2026(conn: asyncpg.Connection) -> Figures:
    return {"ty2026": int(await conn.fetchval(f"SELECT count(*) {_TAX}", TENANT, 2026))}


async def returns(conn: asyncpg.Connection) -> Figures:
    row = await conn.fetchrow(
        "SELECT count(*) AS n, count(DISTINCT engagement_id) AS engagements "
        "FROM tax_returns WHERE tenant_id = $1 AND tax_year = 2025",
        TENANT,
    )
    assert row is not None
    offices = await conn.fetch(
        "SELECT o.name, count(*) FROM tax_returns t JOIN work_items w ON w.id = t.work_item_id "
        "JOIN offices o ON o.id = w.office_id WHERE t.tenant_id = $1 AND t.tax_year = 2025 "
        "GROUP BY 1",
        TENANT,
    )
    return {
        "returns": int(row["n"]),
        "engagements": int(row["engagements"]),
        "offices": {str(r[0]): int(r[1]) for r in offices},
    }


async def named(conn: asyncpg.Connection) -> Figures:
    clients = sorted({client for client, _ in ROWS})
    rows = await conn.fetch(_NAMED, TENANT, clients)
    seen: dict[tuple[str, int], tuple[str, str, str | None]] = {}
    marked: dict[str, tuple[str, str | None]] = {}
    closed: dict[str, str | None] = {}
    for r in rows:
        key = (str(r["client"]), int(r["part"]))
        minutes = key == ("Jonah & Claire Feld", 1)  # "9:12 AM": the only same-day row
        seen[key] = (
            str(r["work_item"]),
            str(r["status"]),
            _local(r["last_client_activity_at"], minutes=minutes),
        )
        if r["marked_done_by"] is not None:
            marked[key[0]] = (str(r["marked_done_by"]), _local(r["marked_done_at"]))
        if r["status"] == "closed":
            closed[key[0]] = _local(r["closed_at"])
    return {
        "rows": seen,
        "marked_done": marked,
        "whitley_closed": closed.get("Marcus & Dana Whitley"),
    }


async def progress(conn: asyncpg.Connection) -> Figures:
    """BND-01's "n of m" for each named row, from the binder's requests (received of all)."""
    clients = sorted({client for client, _ in PROGRESS})
    rows = await conn.fetch(
        "SELECT c.name, l.part, count(i.id) FILTER (WHERE i.status = 'received') AS done, "
        "count(i.id) AS total FROM request_lists l "
        "JOIN tax_returns t ON t.tenant_id = l.tenant_id AND t.work_item_id = l.work_item_id "
        "AND t.tax_year = 2025 JOIN engagements e ON e.id = l.engagement_id "
        "JOIN clients c ON c.id = e.client_id "
        "LEFT JOIN request_items i ON i.request_list_id = l.id "
        "WHERE l.tenant_id = $1 AND c.name = ANY($2::text[]) GROUP BY c.name, l.part",
        TENANT,
        clients,
    )
    return {"progress": {(str(r[0]), int(r[1])): (int(r[2]), int(r[3])) for r in rows}}


async def _binder_of(conn: asyncpg.Connection, client: str) -> uuid.UUID:
    found = await conn.fetchval(
        "SELECT l.id FROM request_lists l JOIN engagements e ON e.id = l.engagement_id "
        "JOIN clients c ON c.id = e.client_id JOIN tax_returns t ON t.tenant_id = l.tenant_id "
        "AND t.work_item_id = l.work_item_id AND t.tax_year = 2025 "
        "WHERE l.tenant_id = $1 AND c.name = $2 AND l.part = 1",
        TENANT,
        client,
    )
    assert found is not None, client
    return cast(uuid.UUID, found)


async def feld(conn: asyncpg.Connection) -> Figures:
    binder = await _binder_of(conn, "Jonah & Claire Feld")
    head = await conn.fetchrow(
        "SELECT l.name, l.status, l.published_at, u.display_name AS published_by "
        "FROM request_lists l LEFT JOIN users u ON u.id = l.published_by WHERE l.id = $1",
        binder,
    )
    assert head is not None
    categories = await conn.fetch(
        "SELECT name FROM request_categories WHERE request_list_id = $1 ORDER BY position",
        binder,
    )
    counts = await conn.fetchrow(
        "SELECT count(*) AS total, count(*) FILTER (WHERE status = 'received') AS done "
        "FROM request_items WHERE request_list_id = $1",
        binder,
    )
    assert counts is not None
    done, total = int(counts["done"]), int(counts["total"])
    return {
        "name": head["name"],
        "status": head["status"],
        "published": (head["published_by"], _local(head["published_at"])),
        "categories": [str(c["name"]) for c in categories],
        "progress": (done, total),
        "percent": round(100 * done / total) if total else None,
        "open": total - done,
    }


async def thornbury(conn: asyncpg.Connection) -> Figures:
    """BND-02 d: 6 of 15, 3 overdue, "Due Aug 31 · 14 days late" at E0."""
    binder = await _binder_of(conn, "Estate of Walter Thornbury")
    row = await conn.fetchrow(
        "SELECT count(*) AS total, count(*) FILTER (WHERE status = 'received') AS done, "
        "count(*) FILTER (WHERE status = 'requested' AND due_on < $2) AS overdue, "
        "min(due_on) FILTER (WHERE status = 'requested' AND due_on < $2) AS due "
        "FROM request_items WHERE request_list_id = $1",
        binder,
        E0.astimezone(ZONE).date(),
    )
    assert row is not None
    due = cast(date | None, row["due"])
    late = (E0.astimezone(ZONE).date() - due).days if due else None
    return {
        "progress": (int(row["done"]), int(row["total"])),
        "overdue": int(row["overdue"]),
        "due": due.isoformat() if due else None,
        "days_late": late,
    }


async def close_intake(conn: asyncpg.Connection) -> Figures:
    """SHL-14 d / CLS-03: Copperleaf's August close intake."""
    rows = await conn.fetch(
        "SELECT i.title, i.status, i.requested_at, i.incorporation_state, w.period_start, "
        "w.due_on, cat.name AS category FROM request_lists l "
        "JOIN work_items w ON w.id = l.work_item_id JOIN engagements e ON e.id = l.engagement_id "
        "JOIN clients c ON c.id = e.client_id JOIN request_items i ON i.request_list_id = l.id "
        "LEFT JOIN request_categories cat ON cat.id = i.category_id "
        "WHERE l.tenant_id = $1 AND l.kind = 'close_intake' "
        "AND c.name = 'Copperleaf Coffee Roasters, Inc.'",
        TENANT,
    )
    asked = [_local(cast(datetime, r["requested_at"])) for r in rows]
    return {
        "requests": len(rows),
        "recurring": asked.count("2026-09-01"),
        "ad_hoc": asked.count("2026-09-11"),
        "received": sum(1 for r in rows if r["status"] == "received"),
        "pending": sorted(
            str(r["title"]) for r in rows if r["incorporation_state"] == "pending_incorporation"
        ),
        "categories": len({r["category"] for r in rows}),
        "due": sorted({cast(date, r["due_on"]).isoformat() for r in rows}),
        "period": sorted({cast(date, r["period_start"]).strftime("%Y-%m") for r in rows}),
    }


async def keystone(conn: asyncpg.Connection) -> Figures:
    """SHL-14 a, b, e: "Requested Sep 1 · due Sep 25"."""
    rows = await conn.fetch(
        "SELECT requested_at, due_on FROM request_items WHERE tenant_id = $1 AND title = $2",
        TENANT,
        KEYSTONE,
    )
    return {
        "letters": [
            (_local(cast(datetime | None, r["requested_at"])), cast(date, r["due_on"]).isoformat())
            for r in rows
        ]
    }


async def granite_peak(conn: asyncpg.Connection) -> Figures:
    """SHL-14 f and SHL-20 a: the Granite Peak FY2026 SURL request, Draft with its run, and the
    31 files that fulfil it, 2 flagged."""
    row = await conn.fetchrow(
        "SELECT i.status, i.drafted_by_run_id IS NOT NULL AS drafted, "
        "(SELECT count(*) FROM evidence_items ev WHERE ev.tenant_id = i.tenant_id "
        "AND ev.engagement_id = i.engagement_id) AS files "
        "FROM request_items i JOIN engagements e ON e.id = i.engagement_id "
        "JOIN clients c ON c.id = e.client_id WHERE i.tenant_id = $1 "
        "AND c.name = 'Granite Peak Outdoor Supply, Inc.' "
        "AND i.title = 'Support for 40 subsequent disbursements (SURL)'",
        TENANT,
    )
    if row is None:
        return {"surl": None}
    return {"surl": (row["status"], row["drafted"]), "files": int(row["files"])}


# --- the loaded tenant --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def own_db(migrated_db: MigratedDatabase) -> Iterator[Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database
    configure_engine(migrated_db.app_url)  # hand the session's database back to later tests


_LOADED: set[str] = set()


@pytest.fixture
async def loaded(own_db: Database, migrated_db: MigratedDatabase) -> AsyncIterator[Database]:
    """E0 plus the `binders` slice, loaded once (on first use) into the module's database."""
    if own_db.superuser_dsn not in _LOADED:
        await dispose_engine()
        configure_engine(own_db.app_url)
        await loader.load(own_db.superuser_dsn, "E0", slices=("binders",), wait=False)
        await dispose_engine()
        configure_engine(migrated_db.app_url)
        _LOADED.add(own_db.superuser_dsn)
    yield own_db


@pytest.fixture
async def conn(loaded: Database) -> AsyncIterator[asyncpg.Connection]:
    async with Seeder(loaded.superuser_dsn).held() as connection:
        yield connection


# --- goldens on the loaded tenant ---------------------------------------------------------------


async def test_ac10_tiles_foot_to_241(conn: asyncpg.Connection) -> None:
    assert await tiles(conn) == {"tiles": TILES, "total": 241}


async def test_ac10_224_returns_and_17_second_parts(conn: asyncpg.Connection) -> None:
    assert await parts(conn) == {"parts": PARTS}


async def test_ac10_224_returns_on_214_engagements_98_64_62_by_office(
    conn: asyncpg.Connection,
) -> None:
    assert await returns(conn) == {
        "returns": 224,
        "engagements": 214,
        "offices": {"Chicago": 98, "Denver": 64, "New York": 62},
    }


async def test_bnd01d_no_ty2026_binders(conn: asyncpg.Connection) -> None:
    assert await ty2026(conn) == {"ty2026": 0}


async def test_bnd01a_named_rows_status_work_item_and_last_activity(
    conn: asyncpg.Connection,
) -> None:
    seen = await named(conn)
    assert seen["rows"] == ROWS
    assert seen["marked_done"] == MARKED_DONE
    assert seen["whitley_closed"] == WHITLEY_CLOSED


async def test_bnd01b_fenwick_is_34_days_silent_at_e0(conn: asyncpg.Connection) -> None:
    last = (await named(conn))["rows"]
    _, _, fenwick = cast(dict[tuple[str, int], tuple[str, str, str]], last)[
        ("Fenwick Family Foundation", 1)
    ]
    assert (E0.astimezone(ZONE).date() - date.fromisoformat(fenwick)).days == 34


async def test_bnd02a_feld_5_of_7_71_percent_nine_categories(conn: asyncpg.Connection) -> None:
    assert await feld(conn) == {
        "name": "2025 Binder",
        "status": "published",
        "published": ("Kevin Osei", "2026-02-03"),  # BND-02 rail: "Feb 3, 2026 · Kevin Osei"
        "categories": FELD_CATEGORIES,
        "progress": (5, 7),
        "percent": 71,
        "open": 2,
    }


async def test_shl14d_copperleaf_close_intake_8_recurring_plus_1_ad_hoc(
    conn: asyncpg.Connection,
) -> None:
    assert await close_intake(conn) == {
        "requests": 9,
        "recurring": 8,
        "ad_hoc": 1,
        "received": 7,
        "pending": [SQUARE],
        "categories": 5,
        "due": ["2026-09-10"],
        "period": ["2026-08"],
    }


async def test_shl14_keystone_bridge_letter_requested_sep_1_due_sep_25(
    conn: asyncpg.Connection,
) -> None:
    assert await keystone(conn) == {"letters": [("2026-09-01", "2026-09-25")]}


@pytest.mark.xfail(
    strict=True,
    reason="DEC-146: only Feld and the close intake carry requests, so Thornbury's 15 are "
    "declared data; recorded in work/tasks/TASK-993-notifications-binder-independent-tests.md "
    "(#380)",
)
async def test_bnd02d_thornbury_6_of_15_with_3_overdue_14_days_late(
    conn: asyncpg.Connection,
) -> None:
    assert await thornbury(conn) == {
        "progress": (6, 15),
        "overdue": 3,
        "due": "2026-08-31",
        "days_late": 14,
    }


@pytest.mark.xfail(
    strict=True,
    reason="DEC-146: only Feld and the close intake carry requests, so the other BND-01 rows' "
    "n of m is declared data; recorded in "
    "work/tasks/TASK-993-notifications-binder-independent-tests.md (#380)",
)
async def test_bnd01a_named_rows_n_of_m_foot_from_their_requests(
    conn: asyncpg.Connection,
) -> None:
    assert await progress(conn) == {"progress": PROGRESS}


@pytest.mark.xfail(
    strict=True,
    reason="the SURL Draft is Thu Sep 24 (SHL-14 f), after this E0 load, and no source names 29 "
    "of its 31 files (SHL-20 names 2) or which payments they support, so the slice seeds no "
    "files (DEC-348's rule); recorded in "
    "work/tasks/TASK-993-notifications-binder-independent-tests.md (#380)",
)
async def test_shl20a_granite_peak_surl_draft_with_31_files(conn: asyncpg.Connection) -> None:
    assert await granite_peak(conn) == {"surl": ("draft", True), "files": 31}


@pytest.mark.xfail(
    strict=True,
    reason="Claire's BND-02 g files are scenario documents the binders slice does not load "
    "yet (F-04-T25's set in TASK-996 has none); recorded in "
    "work/tasks/TASK-993-notifications-binder-independent-tests.md (#380)",
)
async def test_bnd02g_claires_two_files_cover_four_installments(
    conn: asyncpg.Connection,
) -> None:
    """BND-02 g (9:31 AM): Claire's two estimated-payment files land on the Feld request and the
    screening reads "the four TY2025 installments" (Apr 2025 – Jan 2026)."""  # noqa: RUF002
    uploads = await conn.fetchval(
        "SELECT count(*) FROM evidence_versions v JOIN evidence_items ev "
        "ON ev.id = v.evidence_item_id JOIN engagements e ON e.id = ev.engagement_id "
        "JOIN clients c ON c.id = e.client_id WHERE v.tenant_id = $1 "
        "AND c.name = 'Jonah & Claire Feld' AND v.source = 'upload'",
        TENANT,
    )
    assert uploads == 2


# --- BND-01 a, b, d through the public route ----------------------------------------------------

GRACE_SUBJECT: Final = "scenario-grace-holloway"


async def test_bnd01_grace_reads_the_figures_from_get_binders(
    loaded: Database, migrated_db: MigratedDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Grace Holloway (`client_service` on the tax engagements, DEC-20) reads the index at E0."""
    monkeypatch.setenv("ABACUS_IDENTITY_DATABASE_URL", loaded.identity_url)
    settings.cache_clear()
    forget_flags()
    await dispose_engine()
    configure_engine(loaded.app_url)
    idp = FakeIdentityProvider()
    configure_verifier(idp.verifier())
    async with Seeder(loaded.superuser_dsn).held() as connection:
        await connection.execute(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, 'binders.engine', 'true', 'test-seed', 'P-06-T29 E0') "
            "ON CONFLICT DO NOTHING",
            TENANT,
        )
        # DEC-20: Grace's need-to-know is client_service on the tax engagements; the binders
        # slice does not write it (the P-06-T11 index test grants it the same way).
        await connection.execute(
            "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
            "SELECT DISTINCT w.tenant_id, w.engagement_id, u.id, 'client_service' "
            "FROM work_items w, users u WHERE w.tenant_id = $1 AND w.kind = 'tax_return' "
            "AND u.idp_subject = $2 ON CONFLICT DO NOTHING",
            TENANT,
            GRACE_SUBJECT,
        )
    headers = {"Authorization": f"Bearer {idp.token(GRACE_SUBJECT, mfa=True)}"}
    transport = httpx.ASGITransport(app=create_app(), raise_app_exceptions=False)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            with clock.frozen(E0):
                a = await http.get(
                    "/v1/binders",
                    params={"service": "tax_returns", "season": "TY2025", "limit": 15},
                    headers=headers,
                )
                b = await http.get(
                    "/v1/binders",
                    params={
                        "service": "tax_returns",
                        "season": "TY2025",
                        "client_activity": "none_30_days",
                    },
                    headers=headers,
                )
                d = await http.get(
                    "/v1/binders",
                    params={"service": "tax_returns", "season": "TY2026"},
                    headers=headers,
                )
    finally:
        reset_verifier()
        await dispose_engine()
        settings.cache_clear()
        forget_flags()
        monkeypatch.setenv("ABACUS_IDENTITY_DATABASE_URL", migrated_db.identity_url)

    assert a.status_code == 200, a.text
    page = a.json()
    assert page["counts"] == TILES  # BND-01 a: 1 + 48 + 0 + 40 + 152
    assert page["total"] == 241 and len(page["items"]) == 15  # "Showing 15 of 241"
    assert {f["value"]: f["n"] for f in page["facets"]["part"]} == {"1": 224, "2+": 17}
    feld_rows = [r for r in page["items"] if r["client_name"] == "Jonah & Claire Feld"]
    assert [(r["done_count"], r["total_count"]) for r in feld_rows] == [(5, 7)]
    assert b.status_code == 200, b.text
    assert [r["client_name"] for r in b.json()["items"]] == ["Fenwick Family Foundation"]
    assert d.status_code == 200, d.text
    assert (d.json()["items"], d.json()["total"]) == ([], 0)


# --- a seeded change to any figure fails its golden ---------------------------------------------

# One change per figure family, each to a row the golden reads; run inside a rolled-back
# transaction on the loaded tenant.
MUTATIONS: Final[dict[str, tuple[Observer, str]]] = {
    "tiles: a Closed binder becomes Complete": (
        tiles,
        "UPDATE request_lists SET status = 'complete' WHERE id = (SELECT l.id "
        "FROM request_lists l JOIN tax_returns t ON t.tenant_id = l.tenant_id "
        "AND t.work_item_id = l.work_item_id WHERE l.tenant_id = $1 AND t.tax_year = 2025 "
        "AND l.status = 'closed' LIMIT 1)",
    ),
    "parts: a second-part binder is renamed": (
        parts,
        "UPDATE request_lists SET name = '2025 Binder pt 3' WHERE id = (SELECT l.id "
        "FROM request_lists l JOIN tax_returns t ON t.tenant_id = l.tenant_id "
        "AND t.work_item_id = l.work_item_id WHERE l.tenant_id = $1 AND t.tax_year = 2025 "
        "AND l.part = 2 LIMIT 1)",
    ),
    "TY2026: a return moves to tax year 2026": (
        ty2026,
        "UPDATE tax_returns SET tax_year = 2026 WHERE tenant_id = $1 AND work_item_id = "
        "(SELECT l.work_item_id FROM request_lists l JOIN tax_returns t "
        "ON t.tenant_id = l.tenant_id AND t.work_item_id = l.work_item_id "
        "WHERE l.tenant_id = $1 AND t.tax_year = 2025 LIMIT 1)",
    ),
    "returns: a return moves office": (
        returns,
        "UPDATE work_items SET office_id = (SELECT id FROM offices WHERE tenant_id = $1 "
        "AND name = 'Denver') WHERE id = (SELECT w.id FROM work_items w JOIN offices o "
        "ON o.id = w.office_id WHERE w.tenant_id = $1 AND w.kind = 'tax_return' "
        "AND o.name = 'Chicago' LIMIT 1)",
    ),
    "named rows: Whitley's binder is reopened as Published": (
        named,
        "UPDATE request_lists SET status = 'published' WHERE id = (SELECT l.id FROM "
        "request_lists l JOIN engagements e ON e.id = l.engagement_id JOIN clients c "
        "ON c.id = e.client_id WHERE l.tenant_id = $1 AND c.name = 'Marcus & Dana Whitley' "
        "AND l.kind = 'organizer')",
    ),
    "named rows: Fenwick's last client activity moves to Aug 20": (
        named,
        "UPDATE binder_activity SET last_client_activity_at = '2026-08-20 15:00+00' "
        "WHERE binder_id = (SELECT l.id FROM request_lists l JOIN engagements e "
        "ON e.id = l.engagement_id JOIN clients c ON c.id = e.client_id "
        "WHERE l.tenant_id = $1 AND c.name = 'Fenwick Family Foundation')",
    ),
    "Feld: a received request goes back to requested": (
        feld,
        "UPDATE request_items SET status = 'requested' WHERE id = (SELECT i.id FROM "
        "request_items i JOIN request_lists l ON l.id = i.request_list_id JOIN engagements e "
        "ON e.id = l.engagement_id JOIN clients c ON c.id = e.client_id WHERE i.tenant_id = $1 "
        "AND c.name = 'Jonah & Claire Feld' AND l.kind = 'organizer' AND i.status = 'received' "
        "LIMIT 1)",
    ),
    "close intake: Square payouts is incorporated": (
        close_intake,
        "UPDATE request_items SET incorporation_state = 'incorporated', "
        "incorporated_by = created_by, incorporated_at = created_at "
        "WHERE tenant_id = $1 AND title = 'Square payouts — August'",
    ),
    "Keystone: the bridge letter falls due Sep 30": (
        keystone,
        "UPDATE request_items SET due_on = '2026-09-30' WHERE tenant_id = $1 "
        "AND title = 'Bridge letter — Keystone, Oct–Dec 2025'",  # noqa: RUF001
    ),
}


class _Undo(Exception):
    """Raised to leave the change's transaction, which rolls it back."""


@pytest.mark.parametrize("change", sorted(MUTATIONS))
async def test_a_seeded_change_to_a_figure_fails_its_golden(
    conn: asyncpg.Connection, change: str
) -> None:
    observe, sql = MUTATIONS[change]
    before = await observe(conn)
    after: Figures = {}
    with pytest.raises(_Undo):  # leaving the block by an exception rolls the change back
        async with conn.transaction():
            status = await conn.execute(sql, TENANT)
            assert status.split()[-1] != "0", f"{change}: the change touched no row ({status})"
            after = await observe(conn)
            raise _Undo
    assert after and after != before, f"{change}: the golden did not notice"
    assert await observe(conn) == before  # and the loaded tenant is untouched
