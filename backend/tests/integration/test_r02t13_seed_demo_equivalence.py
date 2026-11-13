"""R-02-T13 (TASK-7833): "make seed-demo and fixture mode show identical data". The completion and
governance_room slices are loaded through the loader `make seed-demo` runs, into a database of
their own, and what they wrote is read back against the figures book the portal fixtures foot to
(`apps/web/src/fixtures/seed/portal-r02.foot.test.ts`; DEC-3013, DEC-4807).

Fixture-only by design (not checked here): Copperleaf's posted entries (the portal never posts)
and Meera's K-1 (POR-13's data).
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest

from abacus.kernel.config import settings
from abacus.kernel.db import configure_engine, dispose_engine
from abacus.kernel.flags import forget_flags
from abacus_tools.quality.schema_check import Database, provisioned_database
from abacus_tools.synthetic.scenarios.brightwater_hale import loader
from abacus_tools.synthetic.scenarios.brightwater_hale.loader import (
    BY_LABEL,
    TENANT,
    engagement_id_of,
)

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

BOOK = json.loads(
    (
        Path(__file__).resolve().parents[1]
        / "golden"
        / "scenario"
        / "brightwater_hale"
        / "portal_figures.json"
    ).read_text()
)
ATTEST = BOOK["attest_entries"]


@pytest.fixture(scope="module")
def own_db(migrated_db: MigratedDatabase) -> Iterator[Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database
    configure_engine(migrated_db.app_url)


@pytest.fixture(scope="module")
def loaded(own_db: Database, object_store: str) -> Iterator[Database]:
    del object_store  # the loader writes evidence objects to the test store

    async def load() -> None:
        await dispose_engine()
        configure_engine(own_db.app_url)
        try:
            await loader.load(
                own_db.superuser_dsn,
                "2026-10-21T14:10",
                slices=("completion", "governance_room"),
                wait=False,
            )
        finally:
            await dispose_engine()

    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("ABACUS_IDENTITY_DATABASE_URL", own_db.identity_url)
        settings.cache_clear()
        forget_flags()
        asyncio.run(load())
        yield own_db
    settings.cache_clear()
    forget_flags()


async def _rows(loaded: Database, sql: str, *more: object) -> list[tuple[object, ...]]:
    return [tuple(r) for r in await Seeder(loaded.superuser_dsn).rows(sql, TENANT, *more)]


async def _entry_lines(loaded: Database, ref: str) -> list[tuple[str, Decimal, Decimal]]:
    rows = await _rows(
        loaded,
        "SELECT l.account_code, l.debit, l.credit FROM proposed_entry_lines l "
        "JOIN proposed_entries e ON e.id = l.entry_id WHERE e.tenant_id = $1 AND e.ref = $2 "
        "AND e.work_item_id IN (SELECT id FROM work_items WHERE engagement_id = $3 "
        "AND kind = 'assurance') ORDER BY l.line_no",
        ref,
        engagement_id_of(BY_LABEL["A1"]),
    )
    return [(str(a), Decimal(str(d)), Decimal(str(c))) for a, d, c in rows]


async def test_ac_the_seeded_attest_entries_are_the_books_four(loaded: Database) -> None:
    refs = await _rows(
        loaded,
        "SELECT ref FROM proposed_entries WHERE tenant_id = $1 AND work_item_id IN "
        "(SELECT id FROM work_items WHERE engagement_id = $2 AND kind = 'assurance') "
        "ORDER BY kind, number",
        engagement_id_of(BY_LABEL["A1"]),
    )
    assert sorted(str(r[0]) for r in refs) == sorted(ATTEST["names"])


async def test_ac_aje_1_as_loaded_is_the_books_lines(loaded: Database) -> None:
    def amount(value: str | None) -> Decimal:
        return Decimal(value) if value not in (None, "0") else Decimal(0)

    book = [(x["account"], amount(x["debit"]), amount(x["credit"])) for x in ATTEST["aje_1_lines"]]
    lines = await _entry_lines(loaded, "AJE-1")
    assert lines == book
    assert sum(c for _, _, c in lines) == Decimal(ATTEST["receivable"]["total"])


async def test_ac_paje_2_as_loaded_is_the_books_accrued_group(loaded: Database) -> None:
    (row,) = await _rows(
        loaded,
        "SELECT description FROM proposed_entries WHERE tenant_id = $1 AND ref = 'PAJE-2' "
        "AND work_item_id IN (SELECT id FROM work_items WHERE engagement_id = $2 "
        "AND kind = 'assurance')",
        engagement_id_of(BY_LABEL["A1"]),
    )
    assert row[0] == ATTEST["paje_2_title"]
    lines = await _entry_lines(loaded, "PAJE-2")
    assert [d for _, d, _ in lines if d] == [Decimal(x) for x in ATTEST["accrued"]["lines"]]
    assert sum(c for _, _, c in lines) == Decimal(ATTEST["accrued"]["total"])


async def test_ac_the_governance_room_as_loaded_is_the_books(loaded: Database) -> None:
    book = BOOK["governance"]
    members = await _rows(
        loaded,
        "SELECT c.display_name, m.member_role FROM governance_bodies b "
        "JOIN governance_body_members m ON m.body_id = b.id "
        "JOIN contacts c ON c.id = m.contact_id "
        "WHERE b.tenant_id = $1 AND b.name = $2 ORDER BY m.created_at, c.display_name",
        book["body"],
    )
    assert sorted(str(n) for n, _ in members) == sorted(book["members"])
    assert [str(n) for n, role in members if role == "chair"] == [book["chair"]]
