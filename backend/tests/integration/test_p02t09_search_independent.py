"""P-02-T09 (TASK-7618; ADR-078; C15 v1 `docs/contracts/c15-search.md`; ADR-241): the independent
acceptance suite for P-02-T05 to T08, written from the contract and the epic, not the code.

- Walls (Lena Park, Ashford): no row, no count, no suggestion; the response is identical to a
  corpus without the walled document (INV-3, DEC-43).
- Need-to-know (Grace Holloway): an engagement she is not on contributes nothing.
- Query-time walls: a wall placed after indexing removes the row at once (no reindex).
- Every result opens: each returned row passes its read action's `authorise()`.
- Offshore TRI: a `tri` row the viewer may not read is neither shown nor counted.
- Client roles and the agent are refused by the matrix before the flag is read.
- Withdrawal deletes; the PII scrub keeps a TIN out of a stored title; RLS isolates firms.
- The search text never reaches a log line, and the palette starts no agent run.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import UTC, datetime
from typing import cast

import pytest

from abacus.kernel.config import settings
from abacus.kernel.db import configure_engine, dispose_engine
from abacus.modules.identity.api import RULES, AuthContext, Forbidden
from abacus.modules.platform.search import indexer, query, spec, store
from abacus.modules.platform.search.contract import SearchQueryIn
from abacus.modules.platform.search.spec import SearchIndexDocument, SearchProjection

from .agent_tests.support import Person, Seeder
from .conftest import MigratedDatabase

NOW = datetime(2026, 9, 14, 14, 24, tzinfo=UTC)
SENTINEL = "zqxsentinelfeld"


async def _none(tenant: object, object_id: uuid.UUID) -> SearchIndexDocument | None:
    return None


CLIENTS = SearchProjection(
    object_type="client",
    group="clients",
    read_action="client.read",
    scope_kind="client",
    build=_none,
    target="CLI-02",
)
BINDERS = SearchProjection(
    object_type="binder",
    group="binders",
    read_action="binder.read",
    scope_kind="engagement",
    build=_none,
    target="BND-02",
)
RETURNS = SearchProjection(
    object_type="tax_return",
    group="returns",
    read_action="tax_return.read",
    scope_kind="work_item",
    build=_none,
    target="TAX-02",
    data_class="tri",
)


def _client_doc(client_id: uuid.UUID, title: str) -> SearchIndexDocument:
    return SearchIndexDocument(
        object_id=client_id,
        title=title,
        client_id=client_id,
        source_updated_at=NOW,
        target_params={"clientId": str(client_id)},
    )


def _binder_doc(engagement_id: uuid.UUID, client_id: uuid.UUID, title: str) -> SearchIndexDocument:
    object_id = uuid.uuid4()
    return SearchIndexDocument(
        object_id=object_id,
        title=title,
        context="13 requests open",
        engagement_id=engagement_id,
        client_id=client_id,
        source_updated_at=NOW,
        target_params={"binderId": str(object_id)},
    )


@pytest.fixture(autouse=True)
async def wired(
    migrated_db: MigratedDatabase, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[None]:
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    monkeypatch.setattr(spec, "_PROJECTIONS", {})
    for p in (CLIENTS, BINDERS, RETURNS):
        spec.register(p)
    query._buckets.clear()  # pyright: ignore[reportPrivateUsage] -- a fresh budget per test
    yield
    await dispose_engine()


class World:
    def __init__(self, seed: Seeder) -> None:
        self.seed = seed

    async def build(self) -> World:
        s = self.seed
        self.tenant = await s.firm()
        self.hannah = await s.person(self.tenant)
        self.lena = await s.person(self.tenant)
        self.grace = await s.person(self.tenant)
        feld_entity = await s.entity(self.tenant, "Jonah & Claire Feld")
        ashford_entity = await s.entity(self.tenant, "Ashford Holdings, LLC")
        self.feld = cast(
            uuid.UUID,
            await s.value("SELECT client_id FROM client_entities WHERE id = $1", feld_entity),
        )
        self.ashford = cast(
            uuid.UUID,
            await s.value("SELECT client_id FROM client_entities WHERE id = $1", ashford_entity),
        )
        self.feld_eng = await s.engagement(self.tenant, feld_entity, self.hannah.user_id)
        self.ashford_eng = await s.engagement(self.tenant, ashford_entity, self.hannah.user_id)
        for who in (self.hannah, self.lena):
            await s.member(self.feld_eng, who, "manager")
            await s.member(self.ashford_eng, who, "manager")
        await self.wall(self.lena, self.ashford)
        await store.upsert(self.tenant, CLIENTS, _client_doc(self.feld, "Jonah & Claire Feld"))
        await store.upsert(
            self.tenant, CLIENTS, _client_doc(self.ashford, "Ashford Holdings, LLC")
        )
        self.feld_binder = _binder_doc(self.feld_eng, self.feld, "Feld 2025 PBC requests")
        await store.upsert(self.tenant, BINDERS, self.feld_binder)
        await store.upsert(
            self.tenant,
            BINDERS,
            _binder_doc(self.ashford_eng, self.ashford, "Ashford PBC requests"),
        )
        return self

    async def wall(self, who: Person, client_id: uuid.UUID) -> None:
        await self.seed.run(
            "INSERT INTO ethical_walls (tenant_id, user_id, client_id, created_by) "
            "VALUES ($1, $2, $3, $2)",
            who.tenant_id,
            who.user_id,
            client_id,
        )


def _as(who: Person) -> AuthContext:
    """The person as they sign in: no firm role, so engagement membership decides need-to-know
    (a firm role such as `manager` would read every non-walled engagement, by design)."""
    return who.context()


async def _search(ctx: AuthContext, q: str) -> dict[str, object]:
    out = await query.search(ctx, SearchQueryIn(q=q), agent_mode=False)
    return out.model_dump(mode="json")


@pytest.fixture
async def world(migrated_db: MigratedDatabase) -> World:
    return await World(Seeder(migrated_db.superuser_dsn)).build()


async def test_ac_walls_lena_sees_no_ashford_row_count_or_suggestion(world: World) -> None:
    walled = await _search(_as(world.lena), "ashford")
    assert walled["groups"] == [] and walled["total_visible"] == 0
    assert walled["suggestion"] is None
    typo = await _search(_as(world.lena), "ashfrd holdngs")
    assert typo["suggestion"] is None
    hannah = await _search(_as(world.hannah), "ashford")
    assert cast(int, hannah["total_visible"]) >= 1


async def test_ac_walls_the_response_equals_a_corpus_without_the_document(world: World) -> None:
    before = await _search(_as(world.lena), "holdings")
    await store.delete(world.tenant, "client", world.ashford)
    after = await _search(_as(world.lena), "holdings")
    assert before == after


async def test_ac_need_to_know_grace_sees_no_engagement_she_is_not_on(world: World) -> None:
    grace = await _search(_as(world.grace), "pbc")
    assert all(g["group"] != "binders" for g in grace["groups"])  # type: ignore[index, union-attr] -- a model_dump JSON value


async def test_ac_query_time_wall_removes_the_row_at_once(world: World) -> None:
    assert cast(int, (await _search(_as(world.hannah), "feld"))["total_visible"]) >= 1
    await world.wall(world.hannah, world.feld)
    after = await _search(_as(world.hannah), "feld")
    assert after["groups"] == [] and after["total_visible"] == 0


async def test_ac_every_result_opens(world: World) -> None:
    from abacus.modules.identity.api import authorise

    ctx = _as(world.hannah)
    out = await query.search(ctx, SearchQueryIn(q="feld"), agent_mode=False)
    assert out.groups
    rows = await world.seed.rows(
        "SELECT object_type, object_id, engagement_id, client_id FROM search_documents "
        "WHERE tenant_id = $1",
        world.tenant,
    )
    by_id = {r["object_id"]: dict(r) for r in rows}
    for group in out.groups:
        for item in group.items:
            found = spec.projection(item.object_type)
            assert found is not None
            await authorise(
                ctx, found.read_action, await query.resource_of(by_id[item.object_id], ctx)
            )


async def test_ac_offshore_tri_rows_are_neither_shown_nor_counted(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    work_item = uuid.uuid4()
    await store.upsert(
        world.tenant,
        RETURNS,
        SearchIndexDocument(
            object_id=work_item,
            title="2025 Form 1040",
            context="Jonah & Claire Feld",
            engagement_id=world.feld_eng,
            work_item_id=work_item,
            client_id=world.feld,
            source_updated_at=NOW,
            target_params={"returnId": str(work_item)},
        ),
    )

    async def offshore_refused(ctx: object, action: str, resource: object) -> None:
        if action == "tax_return.read":
            raise Forbidden(action, "relationship")

    monkeypatch.setattr(query, "authorise", offshore_refused)
    out = await _search(_as(world.hannah), "1040")
    assert all(g["group"] != "returns" for g in out["groups"])  # type: ignore[index, union-attr] -- a model_dump JSON value
    assert out["total_visible"] == 0


@pytest.mark.parametrize("role", ["client_admin", "client_contributor", "agent", "system"])
def test_ac_client_roles_and_the_agent_hold_no_search_action(role: str) -> None:
    for action in ("search.read", "search_recent.record"):
        assert RULES[action].decisions.get(role) != "allow", (action, role)


async def test_ac_a_withdrawn_document_is_deleted(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def withdrawn(tenant: object, object_id: uuid.UUID) -> SearchIndexDocument | None:
        return None

    monkeypatch.setattr(spec, "_PROJECTIONS", {})
    spec.register(replace(BINDERS, build=withdrawn))
    assert (
        await indexer.index_object(world.tenant, "binder", world.feld_binder.object_id)
        == "deleted"
    )
    out = await _search(_as(world.hannah), "feld 2025 pbc")
    assert all(g["group"] != "binders" for g in out["groups"])  # type: ignore[index, union-attr] -- a model_dump JSON value


async def test_ac_the_pii_scrub_keeps_a_tin_out_of_a_stored_title(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def tin_named(tenant: object, object_id: uuid.UUID) -> SearchIndexDocument | None:
        return _client_doc(object_id, "Feld 900-45-6789 W-2")

    monkeypatch.setattr(spec, "_PROJECTIONS", {})
    spec.register(replace(CLIENTS, build=tin_named))
    assert await indexer.index_object(world.tenant, "client", world.feld) == "indexed"
    title = await world.seed.value(
        "SELECT title FROM search_documents WHERE object_id = $1", world.feld
    )
    assert "900-45-6789" not in str(title) and "6789" not in str(title)


async def test_ac_rls_another_firm_sees_nothing(world: World) -> None:
    other = await world.seed.firm()
    stranger = await world.seed.person(other)
    out = await _search(_as(stranger), "feld")
    assert out["groups"] == [] and out["total_visible"] == 0


async def test_ac_the_search_text_never_reaches_a_log(
    world: World, caplog: pytest.LogCaptureFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    caplog.set_level(logging.DEBUG)
    await _search(_as(world.hannah), SENTINEL)
    captured = capsys.readouterr()
    assert SENTINEL not in caplog.text
    assert SENTINEL not in captured.out and SENTINEL not in captured.err


async def test_ac_the_palette_starts_no_agent_run(world: World) -> None:
    before = await world.seed.value(
        "SELECT count(*) FROM agent_runs WHERE tenant_id = $1", world.tenant
    )
    await _search(_as(world.hannah), "feld")
    after = await world.seed.value(
        "SELECT count(*) FROM agent_runs WHERE tenant_id = $1", world.tenant
    )
    assert before == after
