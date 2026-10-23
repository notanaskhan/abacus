"""The binders index read model (P-06-T11; C5 v1 `GET /v1/binders`; SPEC-319 AC-10; BND-01).

One read model for BND-01's rows, tiles, totals and facets (R13: no count drift). Every figure
comes from one statement that applies `visible()` (`repository.binder_index`), so a binder the
caller may not read (walled, off the team) is absent from rows, tiles, totals and facets alike,
and no field counts what it hides (INV-3, DEC-43).

Filters (all optional):
- `service`: the work item's kind as BND-01 names it (`tax_returns` is `tax_return`);
- `season`: `TY<year>` for a return (the year its period begins), `FY<year>` for other work;
- `office`, `preparer`: the work item's office and its current preparer;
- `client_activity`: `none_30_days` keeps published binders the client has not touched for
  more than 30 days of business time (their last activity, else their publish);
- `status`: the tile; `counts` leave it out, so a tile never counts itself away;
- `q`: binder name, work item name or client name, case-insensitive.

Each facet leaves out its own filter, so a chip lists its other values with their counts. The
`part` facet splits first binders from second parts ("224 returns · 17 second-part binders").
Rows sort by status (the tiles' order), then newest client activity, then id.

Row status lines (BND-01): the Complete line reads `marked_done_by_name` and `marked_done_at`;
the Closed line `closed_at` and `closed_reason` (a registered rule code); the Count reads
`overdue_count`; "2 requested Sep 8-10" reads `requested_count`, `requested_from` and
`requested_to`. Tags are codes from registered tag providers (the §7216 consents tag is P-07's
and T-01's); none registered, none shown.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from typing import Any, Final, cast
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    ColumnElement,
    Subquery,
    Text,
    case,
    literal,
    or_,
    select,
    tuple_,
)
from sqlalchemy import cast as sql_cast
from sqlalchemy import func as sql_func
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel import clock
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.listing import (
    Facet,
    ListPage,
    Position,
    capped_total,
    clamp_limit,
    decode_cursor,
    envelope,
    query_hash,
    status_counts,
)
from abacus.modules.engagements.api import EngagementRef, get_ref, work_item_index
from abacus.modules.identity.api import AuthContext, allowed_actions, names_of
from abacus.modules.requests.binders import engine_on, unpublish_reason
from abacus.modules.requests.models import BinderActivity, RequestList
from abacus.modules.requests.repository import IndexQuery, binder_index, binder_progress

RESOURCE: Final = "binders"
SILENT_AFTER: Final = timedelta(days=30)
# BND-01's Service chip: the work item kinds, as the screen names them.
SERVICES: Final[dict[str, tuple[str, str]]] = {
    "tax_returns": ("tax_return", "Tax returns"),
    "assurance": ("assurance", "Assurance"),
    "closes": ("close", "Closes"),
    "notices": ("notice", "Notices"),
    "advisory_projects": ("advisory_project", "Advisory projects"),
}
_SERVICE_OF_KIND: Final = {kind: code for code, (kind, _) in SERVICES.items()}
STATUS_ORDER: Final = ("draft", "published", "unpublished", "complete", "closed")
_ROW_ACTIONS: Final = ("binder.read", "binder.update", "binder.publish", "binder.create")
_NEVER: Final = 9_999_999_999  # past any epoch second this list will see

# The tag slot (P-06 §3.2): a provider names, of the binders given, those carrying its tag.
TagProvider = Callable[[TenantContext, Sequence[UUID]], Awaitable[set[UUID]]]
_TAGS: dict[str, TagProvider] = {}


def register_binder_tag(code: str, provider: TagProvider) -> None:
    """Register a row tag once (the §7216 consents tag: P-07 / T-01). Codes, never prose."""
    known = _TAGS.get(code)
    if known is not None and (known.__module__, known.__qualname__) != (
        provider.__module__,
        provider.__qualname__,
    ):
        raise ValueError(f"binder tag {code!r} is already registered")
    _TAGS[code] = provider


@dataclass(frozen=True)
class IndexFilters:
    service: str | None = None
    season: str | None = None
    office: UUID | None = None
    preparer: UUID | None = None
    client_activity: str = "any"
    status: str | None = None
    q: str | None = None


@dataclass(frozen=True)
class BinderIndexRow:
    id: UUID
    engagement_id: UUID
    work_item_id: UUID | None
    client_name: str
    work_item_label: str | None
    name: str
    kind: str
    part: int
    status: str
    preparer_user_id: UUID | None
    done_count: int
    total_count: int
    last_client_activity_at: datetime | None
    unpublished_at: datetime | None
    unpublished_by: UUID | None
    unpublish_reason: str | None
    tags: list[str]
    allowed_actions: list[str]
    service: str | None
    season: str | None
    office_id: UUID | None
    published_at: datetime | None
    marked_done_at: datetime | None
    marked_done_by: UUID | None
    marked_done_by_name: str | None
    closed_at: datetime | None
    closed_reason: str | None
    overdue_count: int
    requested_count: int
    requested_from: date | None
    requested_to: date | None


def _like(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _sort_key() -> ColumnElement[str]:
    """Status in the tiles' order, then newest client activity (none last): one text key, so
    the cursor is one scalar. Fixed-width digits under the C collation sort as numbers."""
    rank = case(
        *((RequestList.status == s, literal(str(n))) for n, s in enumerate(STATUS_ORDER)),
        else_=literal("9"),
    )
    seconds = sql_func.floor(sql_func.extract("epoch", BinderActivity.last_client_activity_at))
    inverted = sql_func.coalesce(literal(_NEVER) - seconds, literal(_NEVER))
    padded = sql_func.lpad(sql_cast(sql_cast(inverted, BigInteger), Text), 10, "0")
    return sql_func.concat(rank, padded).collate("C")


def _filtered(
    ctx: AuthContext,
    filters: IndexFilters,
    silent_before: datetime,
    *,
    without: frozenset[str] = frozenset(),
) -> tuple[IndexQuery, Subquery]:
    index = work_item_index()
    stmt = binder_index(ctx, index)
    if filters.service is not None and "service" not in without:
        kind = SERVICES.get(filters.service, (None, ""))[0]
        stmt = stmt.where(index.c.kind == kind)
    if filters.season is not None and "season" not in without:
        stmt = stmt.where(index.c.season == filters.season)
    if filters.office is not None and "office" not in without:
        stmt = stmt.where(index.c.office_id == filters.office)
    if filters.preparer is not None and "preparer" not in without:
        stmt = stmt.where(index.c.preparer_user_id == filters.preparer)
    if filters.client_activity == "none_30_days" and "client_activity" not in without:
        stmt = stmt.where(
            RequestList.status == "published",
            sql_func.coalesce(BinderActivity.last_client_activity_at, RequestList.published_at)
            < silent_before,
        )
    if filters.q and "q" not in without:
        pattern = _like(filters.q)
        stmt = stmt.where(
            or_(
                RequestList.name.ilike(pattern, escape="\\"),
                index.c.name.ilike(pattern, escape="\\"),
                index.c.client_name.ilike(pattern, escape="\\"),
            )
        )
    if filters.status is not None and "status" not in without:
        stmt = stmt.where(RequestList.status == filters.status)
    return stmt, index


async def _grouped(
    session: AsyncSession,
    stmt: IndexQuery,
    *columns: ColumnElement[Any],  # Any: a facet's value and label columns
) -> list[tuple[Any, ...]]:  # Any: a facet's value and label columns
    sub = (
        stmt.with_only_columns(*(c.label(f"c{n}") for n, c in enumerate(columns)))
        .order_by(None)
        .subquery()
    )
    keys = [sub.c[f"c{n}"] for n in range(len(columns))]
    rows = await session.execute(select(*keys, sql_func.count()).group_by(*keys))
    return [tuple(r) for r in rows]


async def _facets(
    session: AsyncSession, ctx: AuthContext, filters: IndexFilters, silent_before: datetime
) -> dict[str, list[Facet]]:
    def base(facet: str) -> tuple[IndexQuery, Subquery]:
        return _filtered(ctx, filters, silent_before, without=frozenset({facet, "status"}))

    facets: dict[str, list[Facet]] = {}
    stmt, index = base("service")
    services = [
        (_SERVICE_OF_KIND.get(str(kind)), n)
        for kind, n in await _grouped(session, stmt, index.c.kind)
    ]
    facets["service"] = [
        Facet(value=code, label=SERVICES[code][1], n=int(n))
        for code, n in sorted(services, key=lambda s: str(s[0]))
        if code is not None
    ]
    stmt, index = base("season")
    seasons = await _grouped(session, stmt, index.c.season)
    facets["season"] = [
        Facet(value=str(s), label=str(s), n=int(n))
        for s, n in sorted(seasons, key=lambda r: str(r[0]), reverse=True)
        if s is not None
    ]
    stmt, index = base("office")
    offices = await _grouped(session, stmt, index.c.office_id, index.c.office_name)
    facets["office"] = [
        Facet(value=str(o), label=str(name), n=int(n))
        for o, name, n in sorted(offices, key=lambda r: str(r[1]))
        if o is not None and name is not None
    ]
    stmt, index = base("preparer")
    preparers = [
        (UUID(str(p)), int(n))
        for p, n in await _grouped(session, stmt, index.c.preparer_user_id)
        if p is not None
    ]
    names = await names_of([p for p, _ in preparers]) if preparers else {}
    facets["preparer"] = [
        Facet(value=str(p), label=names.get(p, ""), n=n)
        for p, n in sorted(preparers, key=lambda r: names.get(r[0], ""))
    ]
    stmt, _ = base("client_activity")
    every = (await capped_total(session, stmt))[0]
    silent, _ = _filtered(
        ctx,
        replace(filters, client_activity="none_30_days"),
        silent_before,
        without=frozenset({"status"}),
    )
    facets["client_activity"] = [
        Facet(value="any", label="Any", n=every),
        Facet(
            value="none_30_days",
            label="None in 30 days",
            n=(await capped_total(session, silent))[0],
        ),
    ]
    stmt, _ = _filtered(ctx, filters, silent_before, without=frozenset({"status"}))
    parts = await _grouped(
        session, stmt, case((RequestList.part == 1, literal("1")), else_=literal("2+"))
    )
    by_part = {str(p): int(n) for p, n in parts}
    facets["part"] = [
        Facet(value="1", label="Returns", n=by_part.get("1", 0)),
        Facet(value="2+", label="Second-part binders", n=by_part.get("2+", 0)),
    ]
    return facets


async def _tags(tenant: TenantContext, binder_ids: list[UUID]) -> dict[UUID, list[str]]:
    tagged: dict[UUID, list[str]] = {b: [] for b in binder_ids}
    for code in sorted(_TAGS):
        for binder in await _TAGS[code](tenant, binder_ids):
            if binder in tagged:
                tagged[binder].append(code)
    return tagged


async def _row_actions(
    ctx: AuthContext, binder: RequestList, refs: Mapping[UUID, EngagementRef]
) -> list[str]:
    """What the caller may do from the row's menu, as the binder's own record would say."""
    ref = refs[binder.engagement_id]
    resource = replace(ref.resource(), item=None, work_item_id=binder.work_item_id)
    allowed = set(await allowed_actions(ctx, resource, _ROW_ACTIONS))
    if binder.status == "closed":
        allowed -= {"binder.publish", "binder.update"}
    return sorted(allowed)


def _as_date(at: datetime | None) -> date | None:
    """The business date in the firm's zone, as `clock.today` reads it."""
    return at.astimezone(clock.FIRM_ZONE).date() if at is not None else None


async def list_binders(
    ctx: AuthContext, filters: IndexFilters, cursor: str | None, limit: int | None
) -> ListPage[BinderIndexRow]:
    """BND-01: the page, the tiles (`counts` per status) and the facets (C5 v1)."""
    await engine_on(ctx)
    size = clamp_limit(limit)
    query = query_hash(
        service=filters.service,
        season=filters.season,
        office=filters.office,
        preparer=filters.preparer,
        client_activity=filters.client_activity,
        status=filters.status,
        q=filters.q,
    )
    after = (
        decode_cursor(cursor, tenant_id=ctx.tenant_id, resource=RESOURCE, query=query)
        if cursor
        else None
    )
    now = await clock.now(ctx.tenant)
    today = await clock.today(ctx.tenant)
    silent_before = now - SILENT_AFTER
    key = _sort_key()
    async with tenant_session(ctx.tenant) as session:
        untiled, _ = _filtered(ctx, filters, silent_before, without=frozenset({"status"}))
        counts = await status_counts(
            session, untiled, cast(ColumnElement[str], RequestList.status)
        )
        listed, index = _filtered(ctx, filters, silent_before)
        total = await capped_total(session, listed)
        page_stmt = listed.add_columns(key.label("sort_key"))
        if after is not None:
            mark = tuple_(
                literal(str(after.key), type_=Text()).collate("C"),
                sql_cast(literal(after.id, type_=Text()), RequestList.id.type),
            )
            page_stmt = page_stmt.where(tuple_(key, RequestList.id) > mark)
        fetched = list(
            await session.execute(page_stmt.order_by(key, RequestList.id).limit(size + 1))
        )
        facets = await _facets(session, ctx, filters, silent_before)
        page = fetched[:size]
        binders = [cast(RequestList, r[0]) for r in page]
        progress = await binder_progress(session, ctx, [b.id for b in binders], today)
    del index
    following = (
        Position(key=str(page[-1].sort_key), id=str(binders[-1].id))
        if len(fetched) > size and page
        else None
    )
    refs = {e: await get_ref(ctx, e) for e in {b.engagement_id for b in binders}}
    done_by = [b.marked_done_by for b in binders if b.marked_done_by is not None]
    people = await names_of(done_by) if done_by else {}
    tags = await _tags(ctx.tenant, [b.id for b in binders])
    rows: list[BinderIndexRow] = []
    for r, binder in zip(page, binders, strict=True):
        done, every, overdue, waiting, first, last = progress.get(
            binder.id, (0, 0, 0, 0, None, None)
        )
        unpublished = binder.status == "unpublished"
        reason = await unpublish_reason(ctx.tenant_id, binder) if unpublished else None
        rows.append(
            BinderIndexRow(
                id=binder.id,
                engagement_id=binder.engagement_id,
                work_item_id=binder.work_item_id,
                client_name=str(r.client_name or ""),
                work_item_label=r.work_item_name,
                name=binder.name,
                kind=binder.kind,
                part=binder.part,
                status=binder.status,
                preparer_user_id=r.preparer_user_id,
                done_count=done,
                total_count=every,
                last_client_activity_at=r.last_client_activity_at,
                unpublished_at=binder.unpublished_at if unpublished else None,
                unpublished_by=binder.unpublished_by if unpublished else None,
                unpublish_reason=reason,
                tags=tags.get(binder.id, []),
                allowed_actions=await _row_actions(ctx, binder, refs),
                service=_SERVICE_OF_KIND.get(str(r.work_item_kind)),
                season=r.season,
                office_id=r.office_id,
                published_at=binder.published_at,
                marked_done_at=binder.marked_done_at if binder.status == "complete" else None,
                marked_done_by=binder.marked_done_by if binder.status == "complete" else None,
                marked_done_by_name=(
                    people.get(binder.marked_done_by)
                    if binder.status == "complete" and binder.marked_done_by is not None
                    else None
                ),
                closed_at=binder.closed_at if binder.status == "closed" else None,
                closed_reason=binder.closed_reason if binder.status == "closed" else None,
                overdue_count=overdue,
                requested_count=waiting,
                requested_from=_as_date(first),
                requested_to=_as_date(last),
            )
        )
    return envelope(
        rows,
        next_position=following,
        tenant_id=ctx.tenant_id,
        resource=RESOURCE,
        query=query,
        total=total,
        counts={s: counts.get(s, 0) for s in STATUS_ORDER},
        facets=facets,
    )
