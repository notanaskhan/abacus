"""P-02-T13 (TASK-7723; P-02 §10 item 6; ADR-241; DEC-4726): the query plan guard and the
query-count assertion, run in CI on every pull request.

- **Plan guard.** Each group's statement, as `query._group_query` builds it, must be answerable
  from the index: with sequential scans priced out (`enable_seqscan = off`), its plan reads
  `search_documents` only through one of the migration's indexes (the `tsv` GIN, a trigram GIN,
  the tenant/group or tenant/client btree), never a `Seq Scan`. A predicate wrapped so no index
  can serve it (a function over `title`, a cast over `tsv`) fails here before it reaches the 1M
  load test.
- **Query count.** One search issues a fixed number of statements however many rows match: the
  session settings, then per non-empty group its rows and its capped count (no N+1 per row).
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Generator, Iterator
from contextlib import contextmanager
from typing import Any

import pytest
from sqlalchemy import event, text

from abacus.kernel.config import settings
from abacus.kernel.db import configure_engine, dispose_engine, tenant_session
from abacus.kernel.db.session import _current_engine  # pyright: ignore[reportPrivateUsage]
from abacus.modules.platform.search import query, spec, store
from abacus.modules.platform.search.contract import SearchQueryIn

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase
from .test_p02t09_search_independent import (
    BINDERS,
    CLIENTS,
    RETURNS,
    World,
    _as,  # pyright: ignore[reportPrivateUsage]
    _binder_doc,  # pyright: ignore[reportPrivateUsage]
)

INDEXES = frozenset(
    {
        "search_documents_tsv",
        "search_documents_title_trgm",
        "search_documents_related_text_trgm",
        "search_documents_identifiers_text_trgm",
        "search_documents_group",
        "search_documents_client",
    }
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


@pytest.fixture
async def world(migrated_db: MigratedDatabase) -> World:
    return await World(Seeder(migrated_db.superuser_dsn)).build()


def _nodes(plan: dict[str, Any]) -> Iterator[dict[str, Any]]:
    yield plan
    for child in plan.get("Plans", []):
        yield from _nodes(child)


@pytest.mark.parametrize("q", ["feld", "fe", "feld 2025 pbc"])
@pytest.mark.parametrize(("group", "members"), [("clients", (CLIENTS,)), ("binders", (BINDERS,))])
async def test_every_group_statement_is_index_served(
    world: World, group: str, members: tuple[spec.SearchProjection, ...], q: str
) -> None:
    ctx = _as(world.hannah)
    stmt = query._group_query(ctx, group, members, q, 6)  # type: ignore[arg-type]
    assert stmt is not None
    async with tenant_session(ctx.tenant) as session:
        await session.execute(text("SET LOCAL enable_seqscan = off"))
        await session.execute(
            text("SELECT set_config('pg_trgm.similarity_threshold', '0.3', true)")
        )
        conn = await session.connection()
        compiled = stmt.compile(dialect=conn.dialect, compile_kwargs={"render_postcompile": True})
        params = compiled.construct_params()
        args = tuple(params[k] for k in compiled.positiontup or ())
        raw = (await conn.exec_driver_sql(f"EXPLAIN (FORMAT JSON) {compiled}", args)).scalar_one()
    plan = (json.loads(raw) if isinstance(raw, str) else raw)[0]["Plan"]
    on_docs = [n for n in _nodes(plan) if n.get("Relation Name") == "search_documents"]
    assert on_docs, "the plan never reads search_documents"
    assert all(n["Node Type"] != "Seq Scan" for n in on_docs), json.dumps(plan)[:2000]
    used = {n.get("Index Name") for n in _nodes(plan) if "Index Name" in n}
    assert used & INDEXES, f"no search index in the plan: {used}"


@contextmanager
def _counting() -> Generator[list[str]]:
    seen: list[str] = []
    sync = _current_engine().sync_engine

    def before(_c: object, _cur: object, statement: str, *_a: object) -> None:
        seen.append(statement.split(None, 1)[0].upper())

    event.listen(sync, "before_cursor_execute", before)
    try:
        yield seen
    finally:
        event.remove(sync, "before_cursor_execute", before)


async def _count(world: World, q: str) -> int:
    with _counting() as seen:
        await query.search(_as(world.hannah), SearchQueryIn(q=q), agent_mode=False)
    return len(seen)


async def test_the_statement_count_does_not_grow_with_the_rows(world: World) -> None:
    one = await _count(world, "pbc")
    for n in range(12):
        await store.upsert(
            world.tenant, BINDERS, _binder_doc(world.feld_eng, world.feld, f"Feld PBC batch {n}")
        )
    many = await _count(world, "pbc")
    assert many == one, f"{one} statements for one binder, {many} for thirteen"


async def test_the_statement_count_is_bounded_by_the_groups(world: World) -> None:
    registered = len({p.group for p in (CLIENTS, BINDERS, RETURNS)})
    # session settings (statement timeout, trigram threshold, the tenant's RLS settings), then
    # rows and a capped count per group, and one suggestion probe when every group is empty.
    assert await _count(world, "feld") <= 6 + 2 * registered + 1
    assert await _count(world, "zzzz nothing") <= 6 + 2 * registered + 1
