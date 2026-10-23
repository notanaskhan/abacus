"""P-06-T11 against Postgres (SPEC-319 AC-10; P-06 §3.2 Story 2.1; INV-3, DEC-43): "A walled
user's rows, tiles and totals exclude walled binders and no response field reveals a hidden
count."

The read model runs as the app role (grants and row-level security as production uses them);
seed rows go through the superuser (the shared Seeder). The firm is synthetic, so the frozen
business clock is the demo instant, Mon Sep 14, 2026, 9:24 AM Central.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import cast

import pytest

from abacus.kernel import clock
from abacus.kernel.config import settings
from abacus.kernel.db import configure_engine, configure_relay_engine, dispose_engine
from abacus.kernel.errors import NotFound
from abacus.kernel.flags import forget_flags
from abacus.kernel.listing import CursorInvalid, ListPage
from abacus.modules.identity.api import AuthContext, Forbidden
from abacus.modules.requests import binders, contract
from abacus.modules.requests.binder_index import (
    BinderIndexRow,
    IndexFilters,
    list_binders,
    register_binder_tag,
)

from .agent_tests.support import Person, Seeder
from .conftest import MigratedDatabase

T0 = datetime(2026, 9, 14, 14, 24, tzinfo=UTC)  # 9:24 AM Central


@pytest.fixture(autouse=True)
async def engines(
    migrated_db: MigratedDatabase, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[None]:
    monkeypatch.setenv("ABACUS_IDENTITY_DATABASE_URL", migrated_db.identity_url)
    settings.cache_clear()
    forget_flags()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    configure_relay_engine(migrated_db.relay_url)
    yield
    await dispose_engine()
    settings.cache_clear()
    forget_flags()


@pytest.fixture
def seed(migrated_db: MigratedDatabase) -> Seeder:
    return Seeder(migrated_db.superuser_dsn)


@dataclass
class Client:
    id: uuid.UUID
    entity: uuid.UUID
    engagement: uuid.UUID
    returns: list[uuid.UUID] = field(default_factory=list[uuid.UUID])


@dataclass
class Firm:
    seed: Seeder
    tenant: uuid.UUID
    partner: Person
    offices: dict[str, uuid.UUID]

    async def client(self, name: str) -> Client:
        client_id = cast(
            uuid.UUID,
            await self.seed.value(
                "INSERT INTO clients (tenant_id, name) VALUES ($1, $2) RETURNING id",
                self.tenant,
                name,
            ),
        )
        entity = cast(
            uuid.UUID,
            await self.seed.value(
                "INSERT INTO client_entities (tenant_id, client_id, name) "
                "VALUES ($1, $2, $3) RETURNING id",
                self.tenant,
                client_id,
                name,
            ),
        )
        engagement = await self.seed.engagement(self.tenant, entity, self.partner.user_id)
        await self.seed.member(engagement, self.partner, "engagement_partner")
        return Client(client_id, entity, engagement)

    async def tax_return(
        self,
        client: Client,
        *,
        year: int = 2025,
        office: str = "Chicago",
        form: str = "1040",
        start: date | None = None,
    ) -> uuid.UUID:
        begins = start or date(year, 1, 1)
        item = cast(
            uuid.UUID,
            await self.seed.value(
                "INSERT INTO work_items (tenant_id, engagement_id, client_id, client_entity_id, "
                "kind, name, period_start, period_end, office_id, created_by) VALUES ($1, $2, "
                "$3, $4, 'tax_return', $5, $6, $7, $8, $9) RETURNING id",
                self.tenant,
                client.engagement,
                client.id,
                client.entity,
                f"{year} Form {form}",
                begins,
                begins.replace(year=begins.year + 1) - timedelta(days=1),
                self.offices[office],
                self.partner.user_id,
            ),
        )
        await self.seed.run(
            "INSERT INTO tax_returns (tenant_id, work_item_id, engagement_id, client_entity_id, "
            "form, tax_year) VALUES ($1, $2, $3, $4, $5, $6)",
            self.tenant,
            item,
            client.engagement,
            client.entity,
            form,
            begins.year,
        )
        client.returns.append(item)
        return item

    async def binder(
        self,
        client: Client,
        work_item: uuid.UUID,
        status: str,
        *,
        part: int = 1,
        activity: datetime | None = None,
        published: datetime | None = None,
        name: str | None = None,
        done: tuple[uuid.UUID, datetime] | None = None,
        closed: datetime | None = None,
    ) -> uuid.UUID:
        binder = cast(
            uuid.UUID,
            await self.seed.value(
                "INSERT INTO request_lists (tenant_id, engagement_id, work_item_id, name, kind, "
                "part, status, published_at, published_by, marked_done_at, marked_done_by, "
                "closed_at, closed_reason) VALUES ($1, $2, $3, $4, 'organizer', $5, $6, $7, $8, "
                "$9, $10, $11, $12) RETURNING id",
                self.tenant,
                client.engagement,
                work_item,
                name or ("2025 Binder" if part == 1 else f"2025 Binder pt {part}"),
                part,
                status,
                published,
                self.partner.user_id if published is not None else None,
                done[1] if done else None,
                done[0] if done else None,
                closed,
                "work_delivered" if closed is not None else None,
            ),
        )
        await self.seed.run(
            "INSERT INTO binder_activity (tenant_id, binder_id, work_item_id, status, "
            "open_count, last_client_activity_at) VALUES ($1, $2, $3, $4, 0, $5)",
            self.tenant,
            binder,
            work_item,
            status,
            activity,
        )
        return binder

    async def request(
        self,
        client: Client,
        binder: uuid.UUID,
        status: str,
        *,
        due: date | None = None,
        requested_at: datetime | None = None,
    ) -> uuid.UUID:
        item = cast(
            uuid.UUID,
            await self.seed.value(
                "INSERT INTO request_items (tenant_id, engagement_id, request_list_id, "
                "description, audit_area, created_by, client_visible, due_on) "
                "VALUES ($1, $2, $3, 'Brokerage statements', 'Income', $4, true, $5) "
                "RETURNING id",
                self.tenant,
                client.engagement,
                binder,
                self.partner.user_id,
                due,
            ),
        )
        await self.seed.run(
            "UPDATE request_items SET status = $2, requested_at = coalesce($3, requested_at) "
            "WHERE id = $1",
            item,
            status,
            requested_at,
        )
        return item

    async def wall(self, who: Person, client: Client) -> None:
        await self.seed.run(
            "INSERT INTO ethical_walls (tenant_id, user_id, client_id, created_by) "
            "VALUES ($1, $2, $3, $4)",
            self.tenant,
            who.user_id,
            client.id,
            self.partner.user_id,
        )

    async def named(self, display_name: str) -> Person:
        who = await self.seed.person(self.tenant)
        await self.seed.run(
            "UPDATE users SET display_name = $2 WHERE id = $1", who.user_id, display_name
        )
        return who


async def _firm(seed: Seeder, *, engine: bool = True) -> Firm:
    tenant = await seed.firm()
    await seed.run("UPDATE firms SET synthetic = true WHERE tenant_id = $1", tenant)
    if engine:
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, 'binders.engine', 'true', 'test-seed', 'P-06-T11 tests')",
            tenant,
        )
    offices: dict[str, uuid.UUID] = {}
    for name in ("Chicago", "Denver"):
        offices[name] = cast(
            uuid.UUID,
            await seed.value(
                "INSERT INTO offices (tenant_id, name, time_zone) VALUES ($1, $2, "
                "'America/Chicago') RETURNING id",
                tenant,
                name,
            ),
        )
    partner = await seed.person(tenant)
    return Firm(seed, tenant, partner, offices)


TAX_2025 = IndexFilters(service="tax_returns", season="TY2025")


async def _list(
    ctx: AuthContext, filters: IndexFilters = TAX_2025, cursor: str | None = None, limit: int = 50
) -> ListPage[BinderIndexRow]:
    with clock.frozen(T0):
        return await list_binders(ctx, filters, cursor, limit)


def _facet(page: ListPage[BinderIndexRow], name: str) -> dict[str, int]:
    return {f.value: f.n for f in page.facets[name]}


# --- AC-10: visible() everywhere -----------------------------------------------------------------


async def test_ac10_a_walled_clients_binders_are_absent_from_rows_tiles_totals_and_facets(
    seed: Seeder,
) -> None:
    firm = await _firm(seed)
    ashford, granite = await firm.client("Ashford Manufacturing Co."), await firm.client("Granite")
    a_item = await firm.tax_return(ashford)
    g_item = await firm.tax_return(granite, office="Denver")
    g2_item = await firm.tax_return(granite, office="Denver", form="1065")
    await firm.binder(ashford, a_item, "published", activity=T0 - timedelta(days=1))
    walled = {
        await firm.binder(granite, g_item, "draft"),
        await firm.binder(granite, g2_item, "complete", activity=T0 - timedelta(days=40)),
        await firm.binder(
            granite, g2_item, "published", part=2, published=T0 - timedelta(days=60)
        ),
    }
    lena = await seed.person(firm.tenant)
    await seed.member(ashford.engagement, lena, "staff")
    await seed.member(granite.engagement, lena, "staff")

    seen = await _list(lena.context())
    assert seen.total == 3 + 1
    await firm.wall(lena, granite)
    page = await _list(lena.context())

    assert {r.client_name for r in page.items} == {"Ashford Manufacturing Co."}
    assert not walled & {r.id for r in page.items}
    assert page.total == 1 and not page.total_capped
    assert page.counts == {
        "draft": 0,
        "published": 1,
        "unpublished": 0,
        "complete": 0,
        "closed": 0,
    }
    assert _facet(page, "office") == {str(firm.offices["Chicago"]): 1}
    assert _facet(page, "part") == {"1": 1, "2+": 0}
    assert _facet(page, "client_activity") == {"any": 1, "none_30_days": 0}
    assert _facet(page, "season") == {"TY2025": 1}
    # DEC-43: nothing in the envelope sums to more than the caller can see.
    assert sum(page.counts.values()) == page.total
    for facet in ("service", "season", "office", "preparer"):
        assert sum(f.n for f in page.facets[facet]) <= page.total
    # INV-3: a guessed binder is denied at the wall, which the API answers as 404 (app.py).
    with pytest.raises(Forbidden) as denied:
        await binders.read_binder(lena.context(), next(iter(walled)))
    assert denied.value.layer == "wall"


async def test_ac10_a_person_off_the_team_and_another_firm_see_no_binder(seed: Seeder) -> None:
    firm = await _firm(seed)
    feld = await firm.client("Jonah & Claire Feld")
    await firm.binder(feld, await firm.tax_return(feld), "published")
    outsider = await seed.person(firm.tenant)
    other = await _firm(seed)
    for ctx in (outsider.context(), other.partner.context()):
        page = await _list(ctx)
        assert (page.items, page.total) == ([], 0)
        assert set(page.counts.values()) == {0}
        assert _facet(page, "part") == {"1": 0, "2+": 0}
    assert (await _list(firm.partner.context())).total == 1


async def test_ac10_engine_off_answers_404(seed: Seeder) -> None:
    firm = await _firm(seed, engine=False)
    with pytest.raises(NotFound):
        await _list(firm.partner.context())


# --- Story 2.1: tiles, filters and facets --------------------------------------------------------


async def test_story21_tiles_count_without_the_tile_and_total_is_the_tiles_count(
    seed: Seeder,
) -> None:
    firm = await _firm(seed)
    feld = await firm.client("Jonah & Claire Feld")
    item = await firm.tax_return(feld)
    for part, status in enumerate(("draft", "published", "published", "complete", "closed"), 1):
        await firm.binder(feld, item, status, part=part)
    ctx = firm.partner.context()
    every = await _list(ctx)
    published = await _list(ctx, IndexFilters(service="tax_returns", status="published"))
    assert (
        every.counts
        == published.counts
        == {
            "draft": 1,
            "published": 2,
            "unpublished": 0,
            "complete": 1,
            "closed": 1,
        }
    )
    assert (every.total, published.total) == (5, 2)
    assert {r.status for r in published.items} == {"published"}


async def test_story21_none_in_30_days_keeps_published_binders_silent_over_30_days(
    seed: Seeder,
) -> None:
    firm = await _firm(seed)
    fenwick, feld = await firm.client("Fenwick Family Foundation"), await firm.client("Feld")
    shah, osterberg = await firm.client("Meera Shah"), await firm.client("Benjamin Osterberg")
    silent = await firm.binder(
        fenwick,
        await firm.tax_return(fenwick, form="990"),
        "published",
        activity=T0 - timedelta(days=34),
    )
    await firm.binder(feld, await firm.tax_return(feld), "published", activity=T0)
    # Never touched, published 31 days ago: silent too.
    quiet = await firm.binder(
        shah, await firm.tax_return(shah), "published", published=T0 - timedelta(days=31)
    )
    await firm.binder(osterberg, await firm.tax_return(osterberg), "published")  # no facts
    old_done = await firm.tax_return(feld, form="1041")
    await firm.binder(feld, old_done, "complete", activity=T0 - timedelta(days=90))
    page = await _list(
        firm.partner.context(), IndexFilters(service="tax_returns", client_activity="none_30_days")
    )
    assert {r.id for r in page.items} == {silent, quiet}
    assert page.counts["published"] == 2 and page.counts["complete"] == 0
    assert _facet(page, "client_activity") == {"any": 5, "none_30_days": 2}


async def test_story21_service_season_office_preparer_and_search_filter_rows(
    seed: Seeder,
) -> None:
    firm = await _firm(seed)
    lakeshore = await firm.client("Lakeshore Literacy Alliance")
    feld = await firm.client("Jonah & Claire Feld")
    # A fiscal-year 990 (Jul 2025 to Jun 2026) is the 2025 tax year.
    fiscal = await firm.tax_return(lakeshore, form="990", start=date(2025, 7, 1), office="Denver")
    feld25, feld26 = await firm.tax_return(feld), await firm.tax_return(feld, year=2026)
    b_fiscal = await firm.binder(lakeshore, fiscal, "published")
    b_feld = await firm.binder(feld, feld25, "published")
    await firm.binder(feld, feld26, "draft")
    assurance = cast(
        uuid.UUID,
        await seed.value(
            "SELECT id FROM work_items WHERE engagement_id = $1 AND kind = 'assurance'",
            feld.engagement,
        ),
    )
    await firm.binder(feld, assurance, "draft", name="PBC")
    kevin = await firm.named("Kevin Osei")
    await seed.run(
        "INSERT INTO work_item_assignments (tenant_id, work_item_id, engagement_id, user_id, "
        "function, assigned_by) VALUES ($1, $2, $3, $4, 'preparer', $5)",
        firm.tenant,
        feld25,
        feld.engagement,
        kevin.user_id,
        firm.partner.user_id,
    )
    ctx = firm.partner.context()

    season = await _list(ctx)
    assert {r.id for r in season.items} == {b_fiscal, b_feld}
    assert {r.season for r in season.items} == {"TY2025"}
    assert _facet(season, "season") == {"TY2026": 1, "TY2025": 2}
    assert _facet(season, "service") == {"tax_returns": 2}
    assert _facet(season, "preparer") == {str(kevin.user_id): 1}
    assert [f.label for f in season.facets["preparer"]] == ["Kevin Osei"]
    every_service = await _list(ctx, IndexFilters())
    assert _facet(every_service, "service") == {"assurance": 1, "tax_returns": 3}
    assert _facet(every_service, "season")["FY2025"] == 1
    assert {f.label for f in every_service.facets["service"]} == {"Assurance", "Tax returns"}

    denver = await _list(ctx, IndexFilters(office=firm.offices["Denver"]))
    assert [r.id for r in denver.items] == [b_fiscal]
    prepared = await _list(ctx, IndexFilters(preparer=kevin.user_id))
    assert [(r.id, r.preparer_user_id) for r in prepared.items] == [(b_feld, kevin.user_id)]
    for text in ("literacy", "LAKESHORE", "Form 990"):
        found = await _list(ctx, IndexFilters(q=text))
        assert [r.id for r in found.items] == [b_fiscal], text
    assert (await _list(ctx, IndexFilters(q="100%_"))).total == 0


# --- Row facts for BND-01's status lines --------------------------------------------------------


async def test_rows_carry_progress_and_the_facts_of_each_status_line(seed: Seeder) -> None:
    firm = await _firm(seed)
    ridgeline, whitley = await firm.client("Ridgeline"), await firm.client("Whitley")
    thornbury = await firm.client("Estate of Walter Thornbury")
    owen = await firm.named("Owen Calder")
    done_at = datetime(2026, 6, 1, 15, 0, tzinfo=UTC)
    complete = await firm.binder(
        ridgeline,
        await firm.tax_return(ridgeline, form="1065"),
        "complete",
        done=(owen.user_id, done_at),
    )
    closed_at = datetime(2026, 4, 10, 15, 0, tzinfo=UTC)
    closed = await firm.binder(whitley, await firm.tax_return(whitley), "closed", closed=closed_at)
    open_binder = await firm.binder(thornbury, await firm.tax_return(thornbury), "published")
    await firm.request(thornbury, open_binder, "received")
    await firm.request(
        thornbury,
        open_binder,
        "requested",
        due=date(2026, 9, 1),  # overdue on Sep 14
        requested_at=datetime(2026, 9, 9, 15, 0, tzinfo=UTC),
    )
    await firm.request(
        thornbury,
        open_binder,
        "requested",
        due=date(2026, 10, 1),
        requested_at=datetime(2026, 9, 8, 15, 0, tzinfo=UTC),
    )
    await firm.request(
        thornbury,
        open_binder,
        "requested",
        due=date(2026, 10, 1),
        requested_at=datetime(2026, 9, 10, 15, 0, tzinfo=UTC),
    )
    page = await _list(firm.partner.context())
    rows = {r.id: r for r in page.items}

    done = rows[complete]
    assert (done.marked_done_by_name, done.marked_done_at) == ("Owen Calder", done_at)
    assert rows[closed].closed_at == closed_at and rows[closed].closed_reason == "work_delivered"
    assert rows[closed].allowed_actions == ["binder.create", "binder.read"]
    busy = rows[open_binder]
    assert (busy.done_count, busy.total_count, busy.overdue_count) == (1, 4, 1)
    assert busy.requested_count == 3
    assert (busy.requested_from, busy.requested_to) == (date(2026, 9, 8), date(2026, 9, 10))
    assert "binder.publish" in busy.allowed_actions
    assert busy.marked_done_by_name is None and busy.closed_at is None
    # The contract row carries every field the read model gives (additive to C5 v1).
    out = contract.BinderRowOut.model_validate(busy, from_attributes=True)
    assert (out.overdue_count, out.requested_count, out.service) == (1, 3, "tax_returns")


async def test_tags_come_from_registered_providers_only(seed: Seeder) -> None:
    firm = await _firm(seed)
    ferris = await firm.client("Morgan & Kai Ferris")
    tagged = await firm.binder(ferris, await firm.tax_return(ferris), "published")
    untagged = await firm.binder(ferris, await firm.tax_return(ferris, form="1041"), "published")
    assert {tuple(r.tags) for r in (await _list(firm.partner.context())).items} == {()}

    async def consents(_: object, ids: object) -> set[uuid.UUID]:
        return {tagged} & set(cast(list[uuid.UUID], ids))

    register_binder_tag("consents_7216", consents)
    rows = {r.id: r.tags for r in (await _list(firm.partner.context())).items}
    assert rows == {tagged: ["consents_7216"], untagged: []}


# --- Order and cursor ---------------------------------------------------------------------------


async def test_rows_sort_by_status_then_newest_client_activity_and_page_by_cursor(
    seed: Seeder,
) -> None:
    firm = await _firm(seed)
    made: list[tuple[str, int, uuid.UUID]] = []
    for n, (status, days) in enumerate(
        [("published", 5), ("complete", 1), ("published", 1), ("draft", 9), ("published", 30)]
    ):
        client = await firm.client(f"Client {n}")
        binder = await firm.binder(
            client, await firm.tax_return(client), status, activity=T0 - timedelta(days=days)
        )
        made.append((status, days, binder))
    quiet = await firm.client("Client quiet")
    never = await firm.binder(quiet, await firm.tax_return(quiet), "published")
    order = ["draft", "published", "unpublished", "complete", "closed"]
    expected = [b for _, _, b in sorted(made, key=lambda m: (order.index(m[0]), m[1]))]
    expected.insert(4, never)  # published, with no activity: after the published with some
    ctx = firm.partner.context()

    first = await _list(ctx, limit=4)
    assert [r.id for r in first.items] == expected[:4] and first.next_cursor is not None
    second = await _list(ctx, cursor=first.next_cursor, limit=4)
    assert [r.id for r in second.items] == expected[4:] and second.next_cursor is None
    with pytest.raises(CursorInvalid):
        await _list(ctx, IndexFilters(service="tax_returns"), cursor=first.next_cursor)


# --- The projection: the client's mark-done is their last activity -------------------------------


async def test_the_clients_mark_done_becomes_the_binders_last_client_activity(
    seed: Seeder,
) -> None:
    firm = await _firm(seed)
    feld = await firm.client("Jonah & Claire Feld")
    item = await firm.tax_return(feld)
    binder = await firm.binder(
        feld,
        item,
        "published",
        activity=T0 - timedelta(days=40),
        published=T0 - timedelta(days=60),
    )
    claire = await firm.named("Claire Feld")
    await seed.run(
        "UPDATE memberships SET kind = 'client' WHERE tenant_id = $1 AND user_id = $2",
        firm.tenant,
        claire.user_id,
    )
    await seed.run(
        "INSERT INTO client_access_grants (tenant_id, user_id, role, scope_kind, scope_id) "
        "VALUES ($1, $2, 'owner', 'engagement', $3)",
        firm.tenant,
        claire.user_id,
        feld.engagement,
    )
    ctx = firm.partner.context()
    silent = IndexFilters(client_activity="none_30_days")
    assert [r.id for r in (await _list(ctx, silent)).items] == [binder]
    at = T0 + timedelta(hours=1)
    with clock.frozen(at):
        await binders.mark_done(claire.context(), binder)
    page = await _list(ctx)
    assert [(r.status, r.last_client_activity_at) for r in page.items] == [("complete", at)]
    assert page.items[0].marked_done_by_name == "Claire Feld"
    assert (await _list(ctx, silent)).total == 0
    events = await seed.rows(
        "SELECT action FROM audit_events WHERE tenant_id = $1 AND target_id = $2",
        firm.tenant,
        str(binder),
    )
    assert [r["action"] for r in events] == ["binder.marked_done"]
