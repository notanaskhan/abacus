"""C15 v1, the query service (P-02-T08; P-02 §4.3; ADR-241 decisions 5, 6, 7; DEC-4614).

For each registered group in canonical order, up to `limit_per_group + 1` candidates are drawn
from `search_documents` under RLS and the projection's own `visible()` predicate for its scope
kind (`engagement`, `work_item`: the row's engagement; `client`, `client_entity`: its client;
`firm`: the firm role, minus walled clients; `own`: the owner). A `tri` projection's candidates
are re-checked with `authorise()` one by one over a bounded set (four times the limit), so the
offshore consent condition holds without a SQL form. A walled client's documents are never
candidates, so nothing here can count, rank or suggest them (DEC-43).

Matching: the `simple` tsquery over `tsv`, trigram similarity over the title and related names,
and a prefix match over identifiers; one- and two-character queries use the prefix branch only.
Ranking: `ts_rank_cd + similarity(title, q)`, then `source_updated_at` newest first. The statement
runs with `statement_timeout = 1s` and `pg_trgm.similarity_threshold = 0.3`; a timeout answers 503
`search_unavailable`. The suggestion ("Did you mean …?") is the best trigram match over the same
visible predicates, only when every group is empty. `total_visible` counts visible matches, capped
at 99.

The search text is never logged, traced, put in a metric label, an error's facts or an audit row:
nothing in this module logs it, and the errors carry codes only.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass
from threading import Lock
from typing import Final, cast
from uuid import UUID

from sqlalchemy import (
    ColumnElement,
    Select,
    and_,
    column,
    false,
    func,
    literal,
    or_,
    select,
    table,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.exc import DBAPIError

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import NotFound
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    Resource,
    authorise,
    engagement_resource,
    firm_role_allows,
    not_walled_client,
    visible_scope,
)
from abacus.modules.platform.search.contract import (
    TOTAL_VISIBLE_CAP,
    SearchGroupOut,
    SearchItemOut,
    SearchQueryIn,
    SearchResultsOut,
    SearchStatusOut,
    SearchSuggestionOut,
    SearchTargetOut,
)
from abacus.modules.platform.search.errors import (
    SearchQueryInvalid,
    SearchRateLimited,
    SearchUnavailable,
)
from abacus.modules.platform.search.spec import (
    GROUP_ORDER,
    SearchGroup,
    SearchProjection,
    projections,
)

TRI_CANDIDATES: Final = 4  # times limit_per_group: the bounded post-filter set
SIMILARITY: Final = 0.3
SUGGEST_FLOOR: Final = 0.2
_RATE: Final = 10.0  # tokens a second
_BURST: Final = 20.0

docs = table(
    "search_documents",
    column("tenant_id", PgUUID(as_uuid=True)),
    column("object_type"),
    column("object_id", PgUUID(as_uuid=True)),
    column("group_key"),
    column("scope_kind"),
    column("engagement_id", PgUUID(as_uuid=True)),
    column("work_item_id", PgUUID(as_uuid=True)),
    column("client_id", PgUUID(as_uuid=True)),
    column("owner_user_id", PgUUID(as_uuid=True)),
    column("data_class"),
    column("title"),
    column("context"),
    column("identifiers_text"),
    column("related", JSONB),
    column("related_text"),
    column("status_code"),
    column("status_context"),
    column("due_on"),
    column("tag"),
    column("use_count"),
    column("target_params", JSONB),
    column("tsv", TSVECTOR),
    column("source_updated_at"),
)


# --- the per-person budget (10 a second, burst 20) ---------------------------------------------


@dataclass
class _Bucket:
    tokens: float
    at: float


_buckets: dict[tuple[UUID, UUID], _Bucket] = {}
_lock = Lock()


def take_token(ctx: AuthContext) -> None:
    """One query from the person's budget, or 429 `rate_limited` (in-process, per worker)."""
    key = (ctx.tenant_id, ctx.user_id)
    now = time.monotonic()
    with _lock:
        bucket = _buckets.get(key) or _Bucket(_BURST, now)
        bucket.tokens = min(_BURST, bucket.tokens + (now - bucket.at) * _RATE)
        bucket.at = now
        if bucket.tokens < 1:
            _buckets[key] = bucket
            raise SearchRateLimited(facts={"limit": int(_RATE), "retry_after": 1})
        bucket.tokens -= 1
        _buckets[key] = bucket


# --- predicates ----------------------------------------------------------------------------------


def visible_for(ctx: AuthContext, projection: SearchProjection) -> ColumnElement[bool]:
    """The projection's own read predicate on the document's scope columns (fails closed)."""
    action, kind = projection.read_action, projection.scope_kind
    if kind in ("engagement", "work_item"):
        return visible_scope(ctx, action, kind, docs.c.engagement_id)
    if kind in ("client", "client_entity"):
        return visible_scope(ctx, action, kind, docs.c.client_id)
    if kind == "firm":
        if not firm_role_allows(ctx, action):
            return false()
        return not_walled_client(ctx, docs.c.client_id)
    if kind == "own":
        return docs.c.owner_user_id == ctx.user_id
    return false()


def text_predicate(q: str) -> tuple[ColumnElement[bool], ColumnElement[float]]:
    """The match predicate and the rank for search text `q` (already cleaned)."""
    prefix = or_(
        docs.c.title.ilike(f"{_escape(q)}%"), docs.c.identifiers_text.ilike(f"{_escape(q)}%")
    )
    if len(q) <= 2:
        return prefix, literal(0.0)
    tsq = func.websearch_to_tsquery("simple", q)
    predicate = or_(
        docs.c.tsv.op("@@")(tsq),
        docs.c.title.op("%")(q),
        docs.c.related_text.op("%")(q),
        docs.c.identifiers_text.ilike(f"{_escape(q)}%"),
        docs.c.identifiers_text.ilike(f"% {_escape(q)}%"),
    )
    rank = func.ts_rank_cd(docs.c.tsv, tsq) + func.similarity(docs.c.title, q)
    return predicate, rank


def _escape(q: str) -> str:
    return q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _group_query(
    ctx: AuthContext, group: SearchGroup, members: Sequence[SearchProjection], q: str, limit: int
) -> Select[tuple[object, ...]] | None:
    if not members:
        return None
    predicate, rank = text_predicate(q)
    per_type = [and_(docs.c.object_type == p.object_type, visible_for(ctx, p)) for p in members]
    return (
        select(docs, rank.label("rank"))
        .where(docs.c.group_key == group, predicate, or_(*per_type))
        .order_by(rank.desc(), docs.c.source_updated_at.desc(), docs.c.object_id)
        .limit(limit)
    )


# --- shaping -------------------------------------------------------------------------------------


def match_ranges(title: str, q: str) -> list[tuple[int, int]]:
    """`[start, end)` of each query word found in the title, case-insensitive, no overlaps."""
    lowered = title.lower()
    out: list[tuple[int, int]] = []
    for word in sorted({w for w in q.lower().split() if w}, key=len, reverse=True):
        start = lowered.find(word)
        while start != -1:
            end = start + len(word)
            if not any(s < end and start < e for s, e in out):
                out.append((start, end))
            start = lowered.find(word, end)
    return sorted(out)


def context_of(row: dict[str, object], q: str) -> str | None:
    """The row's context; a match on a related party says who it is ("Jonah Feld, limited
    partner 25%")."""
    words = [w for w in q.lower().split() if w]
    title = str(row["title"]).lower()
    if words and not any(w in title for w in words):
        for party in row.get("related") or []:  # type: ignore[union-attr] -- a JSON value read from a row
            name = str(party.get("name", ""))  # type: ignore[union-attr] -- a JSON value read from a row
            if any(w in name.lower() for w in words):
                label = str(party.get("label", ""))  # type: ignore[union-attr] -- a JSON value read from a row
                return f"{name}, {label}" if label else name
    raw = row.get("context")
    return None if raw is None else str(raw)


def item_of(projection: SearchProjection, row: dict[str, object], q: str) -> SearchItemOut:
    status = row.get("status_code")
    return SearchItemOut(
        object_type=projection.object_type,
        object_id=UUID(str(row["object_id"])),
        title=str(row["title"]),
        context=context_of(row, q),
        status=None
        if status is None
        else SearchStatusOut(
            code=str(status),
            context=None if row.get("status_context") is None else str(row["status_context"]),
        ),
        due_on=row.get("due_on"),  # type: ignore[arg-type] -- a test double or the review api's own context alias
        tag=None if row.get("tag") is None else str(row["tag"]),
        use_count=None if row.get("use_count") is None else int(str(row["use_count"])),
        target=SearchTargetOut(
            screen_id=projection.target,
            params={
                str(k): str(v)
                for k, v in cast(dict[str, object], row["target_params"] or {}).items()
            },  # type: ignore[call-overload] -- the row's target params are a JSON object
        ),
        match_ranges=match_ranges(str(row["title"]), q) if q else [],
    )


async def resource_of(row: dict[str, object], ctx: AuthContext) -> Resource:
    """The row's resource for its read action: an engagement's from the engagement row itself
    (archived and all, through identity's engagement slot), else its client's or the firm's."""
    engagement = row.get("engagement_id")
    client = row.get("client_id")
    if engagement is not None:
        return await engagement_resource(ctx.tenant, UUID(str(engagement)))
    if client is not None:
        return Resource.client(ctx.tenant_id, UUID(str(client)))
    return Resource.firm(ctx.tenant_id)


async def _readable(
    ctx: AuthContext, projection: SearchProjection, row: dict[str, object]
) -> bool:
    try:
        await authorise(ctx, projection.read_action, await resource_of(row, ctx))
    except (Forbidden, NotFound):
        return False
    return True


# --- the query -----------------------------------------------------------------------------------


async def search(ctx: AuthContext, body: SearchQueryIn, *, agent_mode: bool) -> SearchResultsOut:
    q = body.q
    agents_only = body.types == ["agents"]
    if not q and not (agents_only and agent_mode):
        raise SearchQueryInvalid()
    if "agents" in (body.types or []) and not agent_mode:
        agents_only = False
    take_token(ctx)
    wanted = set(body.types or GROUP_ORDER)
    if not agent_mode:
        wanted.discard("agents")
    by_group: dict[SearchGroup, list[SearchProjection]] = {}
    for p in projections():
        if p.group in wanted:
            by_group.setdefault(p.group, []).append(p)
    limit = body.limit_per_group
    groups: list[SearchGroupOut] = []
    total = 0
    try:
        async with tenant_session(ctx.tenant) as session:
            await session.execute(text("SET LOCAL statement_timeout = '1s'"))
            await session.execute(
                text("SELECT set_config('pg_trgm.similarity_threshold', :v, true)"),
                {"v": str(SIMILARITY)},
            )
            for group in GROUP_ORDER:
                members = by_group.get(group, [])
                tri = any(p.data_class == "tri" for p in members)
                fetch = (limit * TRI_CANDIDATES if tri else limit) + 1
                stmt = _group_query(ctx, group, members, q, fetch) if q else None
                if stmt is None:
                    continue
                rows = [dict(r) for r in (await session.execute(stmt)).mappings().all()]
                kinds = {p.object_type: p for p in members}
                items: list[SearchItemOut] = []
                for row in rows:
                    projection = kinds.get(str(row["object_type"]))
                    if projection is None:
                        continue
                    if projection.data_class == "tri" and not await _readable(
                        ctx, projection, row
                    ):
                        continue
                    items.append(item_of(projection, row, q))
                if not items:
                    continue
                if tri:
                    total += len(items)  # only rows the viewer passed authorise() for
                else:
                    capped = (
                        stmt.with_only_columns(docs.c.object_id)
                        .order_by(None)
                        .limit(TOTAL_VISIBLE_CAP + 1)
                    )
                    total += int(
                        (
                            await session.execute(
                                select(func.count()).select_from(capped.subquery())
                            )
                        ).scalar_one()
                    )
                groups.append(
                    SearchGroupOut(group=group, items=items[:limit], has_more=len(items) > limit)
                )
            suggestion = (
                await _suggest(session, ctx, [p for ps in by_group.values() for p in ps], q)
                if not groups and q
                else None
            )
    except DBAPIError as exc:
        if "statement timeout" in str(exc.orig) or "canceling statement" in str(exc.orig):
            raise SearchUnavailable() from None
        raise
    return SearchResultsOut(
        groups=groups, suggestion=suggestion, total_visible=min(total, TOTAL_VISIBLE_CAP)
    )


async def _suggest(
    session: object, ctx: AuthContext, members: Sequence[SearchProjection], q: str
) -> SearchSuggestionOut | None:
    """The best trigram match over visible documents only (a typo still gets there)."""
    if len(q) <= 2 or not members:
        return None
    score = func.greatest(
        func.similarity(docs.c.title, q), func.similarity(docs.c.related_text, q)
    )
    per_type = [
        and_(docs.c.object_type == p.object_type, visible_for(ctx, p))
        for p in members
        if p.data_class != "tri"  # a tri suggestion would need the per-row consent check
    ]
    if not per_type:
        return None
    stmt = (
        select(docs.c.object_type, docs.c.title, docs.c.context, docs.c.target_params)
        .where(or_(*per_type), score >= SUGGEST_FLOOR)
        .order_by(score.desc(), docs.c.object_id)
        .limit(1)
    )
    found = (await session.execute(stmt)).mappings().first()  # type: ignore[attr-defined] -- the session is typed object here
    if found is None:
        return None
    row = cast(dict[str, object], found)
    projection = next(p for p in members if p.object_type == row["object_type"])
    return SearchSuggestionOut(
        title=str(row["title"]),
        context=None if row["context"] is None else str(row["context"]),
        target=SearchTargetOut(
            screen_id=projection.target,
            params={
                str(k): str(v)
                for k, v in cast(dict[str, object], row["target_params"] or {}).items()
            },
        ),
    )


__all__ = ["match_ranges", "search", "take_token", "visible_for"]
