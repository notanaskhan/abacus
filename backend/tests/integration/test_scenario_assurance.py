"""A-01-T07 to T10 on the loaded E0 tenant (SPEC-330 AC-16 to AC-27; DEC-310 to DEC-313):
"Loaded E0 foots 27 = 7 + 9 + 6 + 2 + 3", every phase past Planning reached through
`assurance_phase_events` written by A-01's services, and the index, cockpit and Source Documents
read models answer the AUD-01, AUD-02 and AUD-03 figures from the database. Figures are typed
from the A-01 spec, AUD-01/02/03 and blueprint §9.7, not from the code.

The load gets its own database (the session's `migrated_db` holds other loads)."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from uuid import UUID

import pytest

from abacus.kernel import clock
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.flags import forget_flags
from abacus.modules.assurance import cockpit, index
from abacus.modules.identity.api import AuthContext
from abacus.modules.requests.api import source_documents
from abacus_tools.quality.schema_check import Database, provisioned_database
from abacus_tools.synthetic.scenarios.brightwater_hale import loader
from abacus_tools.synthetic.scenarios.brightwater_hale.epochs import DEMO_INSTANT
from abacus_tools.synthetic.scenarios.brightwater_hale.people import FIRM_ROLES, SEATS

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio
TENANT = loader.TENANT


@pytest.fixture(scope="module")
def own_db(migrated_db: MigratedDatabase) -> Iterator[Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database
    configure_engine(migrated_db.app_url)  # hand the session's database back to later tests


@pytest.fixture(scope="module")
def loaded(own_db: Database) -> Database:
    """One E0 load for the module, on its own event loop (the tests then open their own)."""

    async def load() -> None:
        await dispose_engine()
        configure_engine(own_db.app_url)
        try:
            await loader.load(own_db.superuser_dsn, "E0", wait=False)
        finally:
            await dispose_engine()

    asyncio.run(load())
    return own_db


@pytest.fixture(autouse=True)
async def engines(loaded: Database, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[None]:
    monkeypatch.setenv("ABACUS_IDENTITY_DATABASE_URL", loaded.identity_url)
    settings.cache_clear()
    forget_flags()
    await dispose_engine()
    configure_engine(loaded.app_url)
    with clock.frozen(DEMO_INSTANT):
        yield
    await dispose_engine()
    settings.cache_clear()
    forget_flags()


def _person(initials: str) -> AuthContext:
    seat = next(s for s in SEATS if s.initials == initials)
    user = loader.user_id_of(seat)
    return AuthContext(
        TenantContext(TENANT, "human", str(user)),
        user,
        UUID(int=0),
        FIRM_ROLES.get(initials),
        datetime.now(UTC),
    )


async def _work_item(seed: Seeder, label: str) -> UUID:
    found = await seed.value(
        "SELECT id FROM work_items WHERE engagement_id = $1 AND kind = 'assurance'",
        loader.engagement_id_of(loader.BY_LABEL[label]),
    )
    assert isinstance(found, UUID)
    return found


async def _all(ctx: AuthContext, f: index.IndexFilters | None = None) -> list[index.IndexRow]:
    page, _ = await index.audits_index(ctx, f or index.IndexFilters(), cursor=None, limit=200)
    return page.items


# --- A-01-T07 -----------------------------------------------------------------------------------


async def test_ac16_every_phase_past_planning_was_reached_through_events(loaded: Database) -> None:
    seed = Seeder(loaded.superuser_dsn)
    phases = {
        str(r[0]): int(r[1])
        for r in await seed.rows(
            "SELECT phase, count(*) FROM assurance_work_items WHERE tenant_id = $1 GROUP BY 1",
            TENANT,
        )
    }
    assert phases == {
        "planning": 7,
        "fieldwork": 9,
        "in_review": 6,
        "ready_to_release": 2,
        "released": 3,
    }
    # Every item's phase is the last event's target, one step at a time from Planning.
    rows = await seed.rows(
        "SELECT w.work_item_id, w.phase, count(e.id) AS moves, "
        "count(*) FILTER (WHERE e.mode = 'recorded' AND e.actor_kind = 'human') AS recorded, "
        "count(*) FILTER (WHERE e.mode = 'derived' AND e.gate_ref IS NOT NULL) AS derived "
        "FROM assurance_work_items w LEFT JOIN assurance_phase_events e "
        "ON e.tenant_id = w.tenant_id AND e.work_item_id = w.work_item_id "
        "WHERE w.tenant_id = $1 GROUP BY 1, 2",
        TENANT,
    )
    steps = {"planning": 0, "fieldwork": 1, "in_review": 2, "ready_to_release": 3, "released": 4}
    for r in rows:
        assert r["moves"] == steps[r["phase"]], r["phase"]
        assert r["recorded"] == min(r["moves"], 2)
        assert r["derived"] == max(r["moves"] - 2, 0)
    audited = await seed.value(
        "SELECT count(*) FROM audit_events WHERE tenant_id = $1 "
        "AND action IN ('assurance.phase_recorded', 'assurance.phase_derived')",
        TENANT,
    )
    assert audited == sum(steps[p] * n for p, n in phases.items())


async def test_ac17_the_ebp_profile_facts_went_through_the_profile_service(
    loaded: Database,
) -> None:
    seed = Seeder(loaded.superuser_dsn)
    kinds = {
        str(r[0]): int(r[1])
        for r in await seed.rows(
            "SELECT coalesce(ebp_plan_kind, '-'), count(*) FROM assurance_work_items "
            "WHERE tenant_id = $1 GROUP BY 1",
            TENANT,
        )
    }
    assert kinds == {"dc": 12, "403b": 2, "-": 13}
    limited = await seed.value(
        "SELECT count(*) FROM assurance_work_items WHERE tenant_id = $1 AND limited_scope_103a3c",
        TENANT,
    )
    assert limited == 1  # Northwind's §103(a)(3)(C)
    assert (
        await seed.value(
            "SELECT count(*) FROM audit_events WHERE tenant_id = $1 "
            "AND action = 'assurance.profile_updated'",
            TENANT,
        )
        == 14
    )


# --- A-01-T08 -----------------------------------------------------------------------------------


async def test_ac18_the_index_foots_27_with_the_caption_and_segments(loaded: Database) -> None:
    del loaded
    grace = _person("GH")  # firm admin: every audit's metadata
    page, summary = await index.audits_index(grace, index.IndexFilters(), cursor=None, limit=200)
    assert page.total == 27
    assert page.counts == {
        "planning": 7,
        "fieldwork": 9,
        "in_review": 6,
        "ready_to_release": 2,
        "released": 3,
    }
    assert sum(page.counts.values()) == page.total
    assert (summary.ebp, summary.fs_audit, summary.review, summary.compilation_preparation) == (
        14,
        6,
        4,
        3,
    )
    segments = {f.value: f.n for f in page.facets["segment"]}
    assert segments == {"fs": 6, "ebp": 14, "review": 7}  # no SOC & IT or Internal audit
    tiles = [r.phase for r in page.items]
    assert tiles == sorted(tiles, key=index.TILES.index)  # grouped in tile order

    # Pressing Ready to release: 2 rows, the other tiles keep their counts (P-36).
    pressed, _ = await index.audits_index(
        grace, index.IndexFilters(phase="ready_to_release"), cursor=None, limit=200
    )
    assert pressed.total == 2
    assert sorted(r.name for r in pressed.items) == [
        "Cobalt Ridge Manufacturing 401(k) Plan",
        "Halden Health 403(b) Plan",
    ]
    assert pressed.counts == page.counts


async def test_ac20_pbc_report_due_and_the_archive_clock_at_e0(loaded: Database) -> None:
    del loaded
    rows = {r.name: r for r in await _all(_person("GH"))}
    northwind = rows["Northwind Robotics 401(k) Plan"]
    assert northwind.pbc is not None
    assert (northwind.pbc.received, northwind.pbc.total) == (11, 24)
    assert (northwind.partner_initials, northwind.manager_initials) == ("MO", "HL")
    assert northwind.office_name == "Chicago"
    assert (northwind.ebp_plan_kind, northwind.limited_scope_103a3c) == ("dc", True)
    assert str(northwind.report_due_on) == "2026-10-09"
    assert northwind.report_due_tone == "within_30_days"
    # Fairhaven's letter is out: no published PBC binder before G3 (DEC-39).
    assert rows["Fairhaven Foods 401(k) Plan"].pbc is None
    bayside = rows["Bayside Electric Cooperative 401(k) Plan"]
    assert bayside.phase == "released"
    assert str(bayside.released_on) == "2026-07-29"
    assert bayside.archive is not None
    assert (bayside.archive.state, bayside.archive.days_left) == ("archiving", 13)
    meridian = rows["Meridian Tool & Die, Inc."]
    assert meridian.phase == "released"  # archived rows group under Released (DEC-263)
    assert meridian.archive is not None and meridian.archive.state == "archived"
    juniper = rows["Juniper & Oak Interiors, LLC"]
    assert [t.text for t in juniper.tags] == ["No report"]
    oakline = rows["Oakline Software, Inc."]
    assert [t.text for t in oakline.tags] == ["EQR · TW"]
    # Report due in the next 14 days from Sep 14 (kernel.clock).
    soon = await _all(_person("GH"), index.IndexFilters(due="14d"))
    assert all(r.report_due_on is not None for r in soon)
    assert {str(r.report_due_on) for r in soon} <= {"2026-09-18", "2026-09-21", "2026-09-25"} | {
        "2026-09-28"
    }


async def test_ac19_a_member_sees_only_their_engagements_and_the_totals_foot(
    loaded: Database,
) -> None:
    del loaded
    hannah = _person("HL")
    page, summary = await index.audits_index(hannah, index.IndexFilters(), cursor=None, limit=200)
    assert 0 < page.total < 27
    assert sum(page.counts.values()) == page.total
    assert (
        summary.ebp + summary.fs_audit + summary.review + summary.compilation_preparation
        == page.total
    )
    assert sum(f.n for f in page.facets["segment"]) == page.total


# --- A-01-T09, T10 ------------------------------------------------------------------------------


async def test_ac23_northwinds_cockpit_and_source_documents(loaded: Database) -> None:
    seed = Seeder(loaded.superuser_dsn)
    northwind = await _work_item(seed, "A1")
    view = await cockpit.audit_cockpit(_person("HL"), northwind)
    assert view.overview.name == "Northwind Robotics 401(k) Plan"
    assert view.overview.client_name == "Northwind Robotics, Inc."
    assert view.overview.phase == "planning"
    assert view.dock_tabs == ["agent", "viewer"]
    overview = next(b for b in view.bands if b.key == "overview")
    rows = {r.key: r for r in overview.rows}
    assert rows["client"].sub_line == "Northwind Robotics, Inc."
    assert rows["source_documents"].sub_line == "11 of 24 received"
    assert rows["team"].sub_line == "MO · TW · HL · MD · AC"
    assert "methodology" not in rows  # no pinned version at E0: the row hides (fails closed)
    assert "standards_set" not in rows
    assert view.audit_bar.run_started_at is None  # no C6 run provider (DV-11)

    docs = await source_documents(_person("HL"), northwind)
    assert (docs.total, docs.received, docs.needs_review, docs.requested) == (24, 11, 1, 12)
    assert [g.total for g in docs.groups] == [5, 6, 7, 4, 1, 1]
    assert [g.received for g in docs.groups] == [3, 4, 3, 1, 0, 0]
    assert [g.label for g in docs.groups][:2] == ["Plan documents", "Trust / Recordkeeper Reports"]
    first = docs.groups[0].rows[0]
    assert first.status in ("uploaded", "requested")  # Missing first
    dana = [
        r
        for g in docs.groups
        for r in g.rows
        if r.owed_by is not None and r.owed_by.display == "Dana Kowalski"
    ]
    assert dana and all(r.owed_by and r.owed_by.kind == "client_contact" for r in dana)


async def test_ac24_a_metadata_only_reader_gets_the_bar_and_card_alone(loaded: Database) -> None:
    seed = Seeder(loaded.superuser_dsn)
    view = await cockpit.audit_cockpit(_person("GH"), await _work_item(seed, "A1"))
    assert view.overview.name == "Northwind Robotics 401(k) Plan"
    assert (view.bands, view.dock_tabs, view.allowed_actions) == ([], [], [])
    meridian = await cockpit.audit_cockpit(_person("MO"), await _work_item(seed, "A20"))
    assert meridian.read_only_reason == "archived"
    assert meridian.allowed_actions == []
