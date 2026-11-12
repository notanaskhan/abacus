"""C15 v1, the recents service (P-02-T08; P-02 §4.3; ADR-241 decision 8; DEC-4614).

`GET /v1/search/recents` answers the viewer's own last opened records, newest first, re-filtered by
each projection's `visible()` predicate at read time, so a record walled or withdrawn since drops
out silently. `POST /v1/search/recents` resolves the document, re-authorises its read action and
stores it only then (404 otherwise, storing nothing), trimming to 20. Identifiers only; not
audited (operational UI state, P-02 OQ-1).
"""

from __future__ import annotations

from typing import Final

from sqlalchemy import and_, column, or_, select, table
from sqlalchemy.dialects.postgresql import UUID as PgUUID

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import NotFound
from abacus.modules.identity.api import AuthContext, Forbidden, authorise
from abacus.modules.platform.search import store
from abacus.modules.platform.search.contract import (
    SearchItemOut,
    SearchRecentIn,
    SearchRecentRecordedOut,
    SearchRecentsOut,
)
from abacus.modules.platform.search.query import docs, item_of, resource_of, visible_for
from abacus.modules.platform.search.spec import projection, projections

KEEP: Final = 20

recents = table(
    "search_recents",
    column("tenant_id", PgUUID(as_uuid=True)),
    column("user_id", PgUUID(as_uuid=True)),
    column("object_type"),
    column("object_id", PgUUID(as_uuid=True)),
    column("opened_at"),
)


async def read_recents(ctx: AuthContext, limit: int) -> SearchRecentsOut:
    registered = projections()
    if not registered:
        return SearchRecentsOut(items=[])
    visible = or_(
        *(and_(docs.c.object_type == p.object_type, visible_for(ctx, p)) for p in registered)
    )
    stmt = (
        select(docs)
        .join(
            recents,
            and_(
                recents.c.object_type == docs.c.object_type,
                recents.c.object_id == docs.c.object_id,
            ),
        )
        .where(recents.c.user_id == ctx.user_id, visible)
        .order_by(recents.c.opened_at.desc())
        .limit(limit * 2)
    )
    async with tenant_session(ctx.tenant) as session:
        rows = [dict(r) for r in (await session.execute(stmt)).mappings().all()]
    items: list[SearchItemOut] = []
    for row in rows:
        found = projection(str(row["object_type"]))
        if found is None:
            continue
        if found.data_class == "tri":
            try:
                await authorise(ctx, found.read_action, resource_of(row, ctx.tenant_id))
            except Forbidden:
                continue
        items.append(item_of(found, row, ""))
        if len(items) == limit:
            break
    return SearchRecentsOut(items=items)


async def record_recent(ctx: AuthContext, body: SearchRecentIn) -> SearchRecentRecordedOut:
    found = projection(body.object_type)
    if found is None:
        raise NotFound("search_document")
    async with tenant_session(ctx.tenant) as session:
        row = (
            (
                await session.execute(
                    select(docs).where(
                        docs.c.object_type == body.object_type, docs.c.object_id == body.object_id
                    )
                )
            )
            .mappings()
            .first()
        )
    if row is None:
        raise NotFound("search_document")
    try:
        await authorise(ctx, found.read_action, resource_of(dict(row), ctx.tenant_id))
    except Forbidden:
        raise NotFound("search_document") from None
    await store.record_recent(ctx.tenant_id, ctx.user_id, body.object_type, body.object_id, KEEP)
    return SearchRecentRecordedOut(object_type=body.object_type, object_id=body.object_id)


__all__ = ["read_recents", "record_recent"]
