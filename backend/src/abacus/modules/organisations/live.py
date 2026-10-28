"""The clients family, live (P-07-T08 the index; P-07-T09 the record, overview, relationships and
PATCH). Contract: `docs/contracts/clients.md`; spec: SPEC-321 Story 2.

Every read filters through `visible_clients(ctx, "client.read", ...)`: a walled client is absent
from rows, counts, facets and totals and answers 404 by id, and nothing says one is hidden
(INV-3, DEC-43). Facts other modules own come from their registered queries (`slots`); an
unregistered one fails closed. No payload here carries a TIN beyond its masked last four digits.

Last activity is the newest audit event on one of the client's open engagements or about the
client itself (business time). The sort and the "Sep 11 · …" line both use it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Final, Literal, cast
from uuid import UUID

from sqlalchemy import (
    ColumnElement,
    DateTime,
    Select,
    Subquery,
    Text,
    and_,
    func,
    insert,
    literal,
    or_,
    select,
    union_all,
    update,
)
from sqlalchemy import cast as sql_cast
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.listing import (
    Facet,
    ListPage,
    capped_total,
    clamp_limit,
    decode_cursor,
    envelope,
    keyset,
    page_of,
    query_hash,
    status_counts,
)
from abacus.kernel.uow import Ref, Target, audit_activity, uow
from abacus.modules.identity.api import (
    AuthContext,
    Resource,
    allowed_actions,
    authorise,
    engagement_team_query,
    names_of,
    visible,
    visible_clients,
)
from abacus.modules.organisations.events import ClientUpdated
from abacus.modules.organisations.models import (
    Client,
    ClientEntity,
    Contact,
    EntityRelationship,
    Office,
)
from abacus.modules.organisations.service import ClientRecordInvalid, normalise
from abacus.modules.organisations.slots import (
    OverviewItem,
    Profile,
    SectionRows,
    fact_query,
    overview_sections,
)
from abacus.modules.organisations.tin import may_reveal

INDEX: Final = "clients"
RELATIONSHIPS: Final = "client_relationships"
READ: Final = "client.read"
_RECORD_ACTIONS: Final = ("client.update",)
_EPOCH: Final = datetime.fromisoformat("1970-01-01T00:00:00+00:00")
# DEC-62, DEC-138: the Team band's derived Manager and Preparer.
_MANAGER_ROLES: Final = frozenset({"manager"})
_PREPARER_ROLES: Final = frozenset({"senior", "staff"})
_PROFILES: Final[dict[str, Profile]] = {
    "business": "business",
    "nonprofit": "business",
    "trust_family": "household",
    "household": "household",
    "plan_sponsor": "plan_sponsor",
}
_INDIVIDUAL: Final = frozenset({"individual", "household_mfj"})


AnySelect = Select[*tuple[Any, ...]]  # Any: a statement whose row shape the caller names
# "The caller may read the client in this column", for a column other than `Client.id`.
ClientFilter = Callable[[ColumnElement[UUID]], ColumnElement[bool]]


# A person can't make a client a prospect, or a prospect active (the acceptance does). No
# docstring: the error catalogue keeps the engagement's summary for the shared code.
class IllegalTransition(DomainConflict):
    code = "illegal_transition"


class StaleVersion(DomainConflict):
    """The client changed since it was read (`seen_version` is behind): read it again."""

    code = "stale_version"


@dataclass(frozen=True)
class ClientFilters:
    kind: str | None = None
    office_id: UUID | None = None
    partner_id: UUID | None = None
    service_line: str | None = None
    status: str | None = None
    q: str | None = None


# --- shared pieces ------------------------------------------------------------------------------


def _engagements() -> Subquery | None:
    query = fact_query("engagements")
    return None if query is None else query.subquery("client_engagements")


def _latest_activity(engagements: Subquery | None) -> Subquery:
    """`(client_id, at, action)`: each client's newest audit event (business time)."""
    acts = audit_activity().subquery("acts")
    about_client = select(
        Client.id.label("client_id"), acts.c.effective_at, acts.c.action, acts.c.seq
    ).join(
        acts, and_(acts.c.target_type == "client", acts.c.target_id == sql_cast(Client.id, Text))
    )
    parts: list[AnySelect] = [about_client]
    if engagements is not None:
        parts.append(
            select(engagements.c.client_id, acts.c.effective_at, acts.c.action, acts.c.seq).join(
                acts, acts.c.engagement_id == engagements.c.engagement_id
            )
        )
    every = union_all(*parts).subquery("client_acts")
    return (
        select(
            every.c.client_id,
            every.c.effective_at.label("at"),
            every.c.action.label("action"),
        )
        .distinct(every.c.client_id)
        .order_by(every.c.client_id, every.c.effective_at.desc(), every.c.seq.desc())
        .subquery("latest_activity")
    )


def _initials(name: str) -> str:
    words = [w for w in name.replace("-", " ").split() if w[:1].isalpha()]
    if not words:
        return "?"
    return (words[0][0] + (words[-1][0] if len(words) > 1 else "")).upper()


async def _partner_initials(ids: set[UUID]) -> dict[UUID, str]:
    if not ids:
        return {}
    return {uid: _initials(name) for uid, name in (await names_of(sorted(ids))).items()}


def _filters(
    f: ClientFilters, engagements: Subquery | None, *, with_status: bool
) -> list[Any]:  # Any: SQL boolean clauses
    where: list[Any] = []  # Any: SQL boolean clauses
    if f.kind is not None:
        where.append(Client.kind == f.kind)
    if f.office_id is not None:
        where.append(Client.primary_office_id == f.office_id)
    if f.partner_id is not None:
        where.append(Client.relationship_partner_id == f.partner_id)
    if f.service_line is not None:
        if engagements is None:
            where.append(literal(False))  # no service lines registered: no client has one
        else:
            where.append(
                Client.id.in_(
                    select(engagements.c.client_id).where(
                        engagements.c.service_line == f.service_line
                    )
                )
            )
    if with_status and f.status is not None:
        where.append(Client.status == f.status)
    if f.q:
        needle = "%" + normalise(f.q).replace("%", "").replace("_", "") + "%"
        where.append(
            or_(
                Client.normalised_name.like(needle),
                Client.id.in_(
                    select(ClientEntity.client_id).where(ClientEntity.normalised_name.like(needle))
                ),
                Client.id.in_(
                    select(Contact.client_id).where(Contact.normalised_name.like(needle))
                ),
            )
        )
    return where


async def _service_lines(
    session: AsyncSession, engagements: Subquery | None, ids: list[UUID]
) -> dict[UUID, list[str]]:
    if engagements is None or not ids:
        return {}
    rows = await session.execute(
        select(engagements.c.client_id, engagements.c.service_line)
        .where(engagements.c.client_id.in_(ids))
        .distinct()
        .order_by(engagements.c.client_id, engagements.c.service_line)
    )
    out: dict[UUID, list[str]] = {}
    for client_id, line in rows.all():
        out.setdefault(client_id, []).append(line)
    return out


async def _open_requests(
    session: AsyncSession, engagements: Subquery | None, ids: list[UUID]
) -> dict[UUID, int] | None:
    query = fact_query("open_requests")
    if query is None or engagements is None:
        return None
    counts = query.subquery("open_requests")
    rows = await session.execute(
        select(engagements.c.client_id, func.sum(counts.c.n))
        .join(counts, counts.c.engagement_id == engagements.c.engagement_id)
        .where(engagements.c.client_id.in_(ids))
        .group_by(engagements.c.client_id)
    )
    return {client_id: int(n) for client_id, n in rows.all()}


# --- CLI-01 index (P-07-T08) --------------------------------------------------------------------


@dataclass(frozen=True)
class ClientRow:
    id: UUID
    name: str
    descriptor: str | None
    kind: str | None
    status: str
    entity_count: int
    service_lines: list[str]
    is_attest_client: bool
    office_id: UUID | None
    office_name: str | None
    relationship_partner_id: UUID | None
    relationship_partner_initials: str | None
    portal_status: str
    open_request_count: int | None
    last_activity_at: datetime | None
    last_activity_event_type: str | None
    allowed_actions: list[str]


async def list_clients(
    ctx: AuthContext,
    f: ClientFilters,
    *,
    sort: Literal["last_activity", "name"],
    facets: bool,
    cursor: str | None,
    limit: int | None,
) -> ListPage[ClientRow]:
    limit = clamp_limit(limit)
    digest = query_hash(filters=f.__dict__, sort=sort)  # `q` is hashed, never logged
    after = (
        decode_cursor(cursor, tenant_id=ctx.tenant_id, resource=INDEX, query=digest)
        if cursor
        else None
    )
    seen = await visible_clients(ctx, READ, Client.id)
    engagements = _engagements()
    latest = _latest_activity(engagements)
    entity_count = (
        select(func.count())
        .select_from(ClientEntity)
        .where(ClientEntity.client_id == Client.id)
        .correlate(Client)
        .scalar_subquery()
    )
    sort_key = (
        func.coalesce(latest.c.at, literal(_EPOCH, type_=DateTime(timezone=True)))
        if sort == "last_activity"
        else Client.normalised_name
    )
    base = (
        select(
            Client,
            Office.name,
            entity_count.label("entity_count"),
            latest.c.at,
            latest.c.action,
            sort_key.label("sort_key"),
        )
        .outerjoin(Office, Office.id == Client.primary_office_id)
        .outerjoin(latest, latest.c.client_id == Client.id)
        .where(seen, *_filters(f, engagements, with_status=False))
    )
    rows_stmt = base.where(*_status(f))
    async with tenant_session(ctx.tenant) as session:
        fetched = (
            await session.execute(
                keyset(
                    rows_stmt,
                    sort=cast(ColumnElement[object], sort_key),
                    id_column=cast(ColumnElement[object], Client.id.expression),
                    after=after,
                    descending=sort == "last_activity",
                    limit=limit,
                )
            )
        ).all()
        page, next_at = page_of(fetched, limit=limit, key=lambda r: r[5], id_of=lambda r: r[0].id)
        total = await capped_total(session, cast(Select[Any], rows_stmt))  # Any: counted only
        tiles = cast(Select[Any], base)  # Any: only the status column is read
        counts = await status_counts(session, tiles, Client.status.expression)
        ids = [r[0].id for r in page]
        lines = await _service_lines(session, engagements, ids)
        open_counts = await _open_requests(session, engagements, ids)
        found_facets = (
            await _facets(session, base.where(*_status(f)), engagements) if facets else {}
        )
    initials = await _partner_initials(
        {r[0].relationship_partner_id for r in page if r[0].relationship_partner_id}
    )
    actions = sorted(await allowed_actions(ctx, Resource.firm(ctx.tenant_id), ("client.update",)))
    items = [
        ClientRow(
            id=c.id,
            name=c.name,
            descriptor=c.descriptor,
            kind=c.kind,
            status=c.status,
            entity_count=int(n),
            service_lines=lines.get(c.id, []),
            is_attest_client=c.is_attest_client,
            office_id=c.primary_office_id,
            office_name=office,
            relationship_partner_id=c.relationship_partner_id,
            relationship_partner_initials=(
                initials.get(c.relationship_partner_id) if c.relationship_partner_id else None
            ),
            portal_status=c.portal_status,
            open_request_count=None if open_counts is None else open_counts.get(c.id, 0),
            last_activity_at=at,
            last_activity_event_type=action,
            allowed_actions=actions,
        )
        for c, office, n, at, action, _key in page
    ]
    return envelope(
        items,
        next_position=next_at,
        tenant_id=ctx.tenant_id,
        resource=INDEX,
        query=digest,
        total=total,
        counts=counts,
        facets=found_facets,
    )


def _status(f: ClientFilters) -> list[Any]:  # Any: SQL boolean clauses
    return [] if f.status is None else [Client.status == f.status]


async def _facets(
    session: AsyncSession,
    stmt: AnySelect,  # the index's rows; only their client columns are read
    engagements: Subquery | None,
) -> dict[str, list[Facet]]:
    rows = stmt.with_only_columns(
        Client.id, Client.kind, Client.primary_office_id, Client.relationship_partner_id
    ).subquery("facet_rows")
    out: dict[str, list[Facet]] = {}

    async def grouped(column: ColumnElement[Any]) -> list[tuple[Any, int]]:  # Any: facet values
        result = await session.execute(
            select(column, func.count()).where(column.is_not(None)).group_by(column)
        )
        return [(value, int(n)) for value, n in result.all()]

    out["kind"] = [Facet(value=k, label=k, n=n) for k, n in sorted(await grouped(rows.c.kind))]
    offices = dict((await session.execute(select(Office.id, Office.name))).tuples().all())
    out["office"] = sorted(
        (
            Facet(value=str(o), label=offices.get(o, ""), n=n)
            for o, n in await grouped(rows.c.primary_office_id)
        ),
        key=lambda x: x.label,
    )
    partners = await grouped(rows.c.relationship_partner_id)
    names = await names_of([p for p, _ in partners]) if partners else {}
    out["partner"] = sorted(
        (Facet(value=str(p), label=names.get(p, ""), n=n) for p, n in partners),
        key=lambda x: x.label,
    )
    if engagements is None:
        out["service_line"] = []
    else:
        result = await session.execute(
            select(engagements.c.service_line, func.count(func.distinct(rows.c.id)))
            .join(engagements, engagements.c.client_id == rows.c.id)
            .group_by(engagements.c.service_line)
            .order_by(engagements.c.service_line)
        )
        out["service_line"] = [Facet(value=s, label=s, n=int(n)) for s, n in result.all()]
    return out


# --- CLI-02 record (P-07-T09) -------------------------------------------------------------------


@dataclass(frozen=True)
class EntityBrief:
    id: UUID
    name: str
    entity_type: str | None
    fye_month_day: str | None
    state_of_formation: str | None
    plan_number: str | None
    tin_kind: str | None  # None: no TIN on file or applied for
    tin_presence: str | None
    tin_last4: str | None


@dataclass(frozen=True)
class EngagementBrief:
    id: UUID
    name: str
    status: str
    service_line: str


@dataclass(frozen=True)
class ClientRecordView:
    client: Client
    office_name: str | None
    manager_user_ids: list[UUID]
    preparer_user_ids: list[UUID]
    entities: list[EntityBrief]
    active_engagements: list[EngagementBrief]
    tab_counts: dict[str, int | None]
    allowed_actions: list[str]


async def _visible_client(session: AsyncSession, ctx: AuthContext, client_id: UUID) -> Client:
    """The client if the caller may read it; 404 for a walled or unknown one (DEC-43)."""
    seen = await visible_clients(ctx, READ, Client.id)
    found = (
        await session.execute(select(Client).where(Client.id == client_id, seen))
    ).scalar_one_or_none()
    if found is None:
        raise NotFound("client")
    return found


async def readable_client(ctx: AuthContext, client_id: UUID) -> None:
    """404 unless the caller may read the client: a walled and an unknown client answer alike
    (DEC-43); for another module's read scoped to one client (P-07-T57's Activity lines)."""
    async with tenant_session(ctx.tenant) as session:
        await _visible_client(session, ctx, client_id)


def _tin(entity: ClientEntity) -> tuple[str | None, str | None, str | None]:
    if entity.tin_status == "none":
        return None, None, None
    kind = entity.tin_kind or ("ssn" if entity.entity_type in _INDIVIDUAL else "ein")
    return kind, entity.tin_status, entity.tin_last4


async def client_record(ctx: AuthContext, client_id: UUID) -> ClientRecordView:
    engagements = _engagements()
    async with tenant_session(ctx.tenant) as session:
        client = await _visible_client(session, ctx, client_id)
        office = (
            await session.execute(select(Office.name).where(Office.id == client.primary_office_id))
        ).scalar_one_or_none()
        entities = (
            (
                await session.execute(
                    select(ClientEntity)
                    .where(ClientEntity.client_id == client_id)
                    .order_by(ClientEntity.name, ClientEntity.id)
                )
            )
            .scalars()
            .all()
        )
        managers: list[UUID] = []
        preparers: list[UUID] = []
        briefs: list[EngagementBrief] = []
        if engagements is not None:
            team = engagement_team_query().subquery("team")
            members = await session.execute(
                select(team.c.user_id, team.c.role)
                .join(engagements, engagements.c.engagement_id == team.c.engagement_id)
                .where(engagements.c.client_id == client_id)
                .distinct()
                .order_by(team.c.user_id)
            )
            for user_id, role in members.all():
                if role in _MANAGER_ROLES and user_id not in managers:
                    managers.append(user_id)
                if role in _PREPARER_ROLES and user_id not in preparers:
                    preparers.append(user_id)
            shown = await session.execute(
                select(
                    engagements.c.engagement_id,
                    engagements.c.name,
                    engagements.c.status,
                    engagements.c.service_line,
                )
                .where(
                    engagements.c.client_id == client_id,
                    visible(ctx, "engagement.read_metadata", engagements.c.engagement_id),
                )
                .order_by(engagements.c.name, engagements.c.engagement_id)
            )
            briefs = [EngagementBrief(*row) for row in shown.all()]
        relationships = await _relationship_count(session, ctx, client_id)
        contacts = int(
            (
                await session.execute(
                    select(func.count()).select_from(Contact).where(Contact.client_id == client_id)
                )
            ).scalar_one()
        )
    actions = set(
        await allowed_actions(ctx, Resource.client(ctx.tenant_id, client_id), _RECORD_ACTIONS)
    )
    # P-07-T10: `tin.reveal` is held through an engagement role on one of the client's open
    # engagements, never on the client itself (DEC-223).
    if await may_reveal(ctx, client_id):
        actions.add("tin.reveal")
    return ClientRecordView(
        client=client,
        office_name=office,
        manager_user_ids=managers,
        preparer_user_ids=preparers,
        entities=[
            EntityBrief(
                e.id,
                e.name,
                e.entity_type,
                e.fye_month_day,
                e.state_of_formation,
                e.plan_number,
                *_tin(e),
            )
            for e in entities
        ],
        active_engagements=briefs,
        tab_counts={
            "engagements": len(briefs),
            "relationships": relationships,
            "contacts": contacts,
            "messages": None,  # no owner registers a message count yet
        },
        allowed_actions=sorted(actions),
    )


# --- overview -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class OverviewSectionView:
    code: str
    kind: str
    read_action: str
    rows: SectionRows


async def client_overview(
    ctx: AuthContext, client_id: UUID
) -> tuple[Profile, list[OverviewSectionView]]:
    """The kind's profile and the sections the caller may read, each by its own action."""
    async with tenant_session(ctx.tenant) as session:
        client = await _visible_client(session, ctx, client_id)
    profile: Profile = _PROFILES.get(client.kind or "", "empty")
    resource = Resource.client(ctx.tenant_id, client_id)
    out: list[OverviewSectionView] = []
    for section in overview_sections(profile):
        if section.read_action not in await allowed_actions(ctx, resource, (section.read_action,)):
            continue  # a metadata-only role gets metadata sections (ADR-024)
        rows = await section.provide(ctx, client_id)
        out.append(OverviewSectionView(section.code, section.kind, section.read_action, rows))
    return profile, out


async def entities_section(ctx: AuthContext, client_id: UUID) -> SectionRows:
    """The client's entities, one details row each (organisations' own section)."""
    async with tenant_session(ctx.tenant) as session:
        rows = (
            await session.execute(
                select(ClientEntity.id, ClientEntity.name, ClientEntity.entity_type)
                .where(ClientEntity.client_id == client_id)
                .order_by(ClientEntity.name, ClientEntity.id)
            )
        ).all()
    return SectionRows(
        [
            OverviewItem(key=kind or "entity", text=name, ref_type="client_entity", ref_id=eid)
            for eid, name, kind in rows
        ],
        total=len(rows),
    )


async def key_dates_section(ctx: AuthContext, client_id: UUID) -> SectionRows:
    """Each entity's fiscal year end (`MM-DD`), as a key date row."""
    async with tenant_session(ctx.tenant) as session:
        rows = (
            await session.execute(
                select(ClientEntity.id, ClientEntity.name, ClientEntity.fye_month_day)
                .where(
                    ClientEntity.client_id == client_id, ClientEntity.fye_month_day.is_not(None)
                )
                .order_by(ClientEntity.fye_month_day, ClientEntity.name)
            )
        ).all()
    return SectionRows(
        [
            OverviewItem(
                key="fiscal_year_end",
                text=name,
                figure=fye,
                ref_type="client_entity",
                ref_id=eid,
            )
            for eid, name, fye in rows
        ]
    )


async def contacts_section(ctx: AuthContext, client_id: UUID) -> SectionRows:
    async with tenant_session(ctx.tenant) as session:
        rows = (
            await session.execute(
                select(Contact.id, Contact.display_name, Contact.contact_kind)
                .where(Contact.client_id == client_id)
                .order_by(Contact.display_name, Contact.id)
                .limit(5)
            )
        ).all()
        total = int(
            (
                await session.execute(
                    select(func.count()).select_from(Contact).where(Contact.client_id == client_id)
                )
            ).scalar_one()
        )
    return SectionRows(
        [
            OverviewItem(key=kind, text=name, ref_type="contact", ref_id=cid)
            for cid, name, kind in rows
        ],
        total=total,
    )


# --- relationships ------------------------------------------------------------------------------


@dataclass(frozen=True)
class RelationshipView:
    id: UUID
    kind: str
    from_entity_id: UUID
    from_entity_name: str
    to_entity_id: UUID
    to_entity_name: str
    to_client_id: UUID
    percent: str | None
    effective_from: date | None
    effective_to: date | None


def _edges(client_id: UUID, seen_other: ClientFilter) -> AnySelect:  # the edge rows
    """The client's edges, either direction, whose other end the caller may read: an edge into
    a walled client is omitted, never redacted (INV-3)."""
    mine = select(ClientEntity.id).where(ClientEntity.client_id == client_id)
    src = ClientEntity.__table__.alias("src")
    dst = ClientEntity.__table__.alias("dst")
    other_client = func.coalesce(func.nullif(dst.c.client_id, client_id), src.c.client_id)
    return (
        select(
            EntityRelationship.id,
            EntityRelationship.kind,
            EntityRelationship.from_entity_id,
            src.c.name,
            EntityRelationship.to_entity_id,
            dst.c.name,
            dst.c.client_id,
            EntityRelationship.percent,
            EntityRelationship.effective_from,
            EntityRelationship.effective_to,
        )
        .join(src, src.c.id == EntityRelationship.from_entity_id)
        .join(dst, dst.c.id == EntityRelationship.to_entity_id)
        .where(
            or_(
                EntityRelationship.from_entity_id.in_(mine),
                EntityRelationship.to_entity_id.in_(mine),
            ),
            seen_other(other_client),
        )
    )


async def _relationship_count(session: AsyncSession, ctx: AuthContext, client_id: UUID) -> int:
    seen = await _seen_clients(ctx)
    stmt = _edges(client_id, seen)
    return int(
        (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    )


async def _seen_clients(ctx: AuthContext) -> ClientFilter:
    """A builder for "the caller may read this client", for a column other than `Client.id`."""
    seen = await visible_clients(ctx, READ, Client.id)
    readable = select(Client.id).where(seen)

    def admits(column: ColumnElement[UUID]) -> ColumnElement[bool]:
        return column.in_(readable)

    return admits


async def client_relationships(
    ctx: AuthContext, client_id: UUID, cursor: str | None
) -> ListPage[RelationshipView]:
    limit = clamp_limit(None)
    digest = query_hash(client_id=str(client_id))
    after = (
        decode_cursor(cursor, tenant_id=ctx.tenant_id, resource=RELATIONSHIPS, query=digest)
        if cursor
        else None
    )
    async with tenant_session(ctx.tenant) as session:
        await _visible_client(session, ctx, client_id)
        stmt = _edges(client_id, await _seen_clients(ctx))
        fetched = (
            await session.execute(
                keyset(
                    stmt,
                    sort=cast(ColumnElement[object], EntityRelationship.effective_from.expression),
                    id_column=cast(ColumnElement[object], EntityRelationship.id.expression),
                    after=after,
                    limit=limit,
                )
            )
        ).all()
        page, next_at = page_of(fetched, limit=limit, key=lambda r: r[8], id_of=lambda r: r[0])
        total = await capped_total(session, cast(Select[Any], stmt))  # Any: counted only
    items = [
        RelationshipView(
            id=r[0],
            kind=r[1],
            from_entity_id=r[2],
            from_entity_name=r[3],
            to_entity_id=r[4],
            to_entity_name=r[5],
            to_client_id=r[6],
            percent=None if r[7] is None else format(r[7].normalize(), "f"),
            effective_from=r[8],
            effective_to=r[9],
        )
        for r in page
    ]
    return envelope(
        items,
        next_position=next_at,
        tenant_id=ctx.tenant_id,
        resource=RELATIONSHIPS,
        query=digest,
        total=total,
    )


@dataclass(frozen=True)
class NewRelationship:
    from_entity_id: UUID
    to_entity_id: UUID
    kind: str
    effective_from: date
    percent: str | None = None
    effective_to: date | None = None


async def add_relationship(ctx: AuthContext, relationship: NewRelationship) -> UUID:
    """A new edge between two of the firm's entities, by a person who may update the client of
    the `from` entity (CLI-03 and T-06 call it). One `entity_relationship.created` event."""
    async with tenant_session(ctx.tenant) as session:
        owner = (
            await session.execute(
                select(ClientEntity.client_id).where(
                    ClientEntity.id == relationship.from_entity_id
                )
            )
        ).scalar_one_or_none()
        if owner is None:
            raise NotFound("client_entity")
        await _visible_client(session, ctx, owner)
    await authorise(ctx, "client.update", Resource.client(ctx.tenant_id, owner))
    async with uow(ctx.tenant) as tx:
        try:
            async with tx.session.begin_nested():
                edge = (
                    await tx.session.execute(
                        insert(EntityRelationship)
                        .values(
                            tenant_id=ctx.tenant_id,
                            from_entity_id=relationship.from_entity_id,
                            to_entity_id=relationship.to_entity_id,
                            kind=relationship.kind,
                            percent=relationship.percent,
                            effective_from=relationship.effective_from,
                            effective_to=relationship.effective_to,
                            created_by=ctx.user_id,
                        )
                        .returning(EntityRelationship.id)
                    )
                ).scalar_one()
        except IntegrityError:
            raise NotFound("client_entity") from None  # another firm's entity, or a bad edge
        tx.record("entity_relationship.created", target=Target("client", owner))
    return edge


# --- PATCH --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ClientPatch:
    seen_version: int
    descriptor: str | None = None
    primary_office_id: UUID | None = None
    relationship_partner_id: UUID | None = None
    status: str | None = None


def _legal(current: str, target: str) -> bool:
    """A person can't make a client a prospect, or a prospect active (the acceptance does)."""
    return target == current or not (
        target == "prospect" or (current == "prospect" and target == "active")
    )


async def update_client(ctx: AuthContext, client_id: UUID, patch: ClientPatch) -> None:
    """Descriptor, office, relationship partner and status; 409 on a stale version or an
    illegal transition; one `client.updated` audit event and outbox event naming the fields."""
    async with tenant_session(ctx.tenant) as session:
        client = await _visible_client(session, ctx, client_id)
    await authorise(ctx, "client.update", Resource.client(ctx.tenant_id, client_id))
    values: dict[str, object] = {}
    if patch.descriptor is not None and patch.descriptor != client.descriptor:
        values["descriptor"] = patch.descriptor
    if patch.primary_office_id is not None and patch.primary_office_id != client.primary_office_id:
        values["primary_office_id"] = patch.primary_office_id
    if (
        patch.relationship_partner_id is not None
        and patch.relationship_partner_id != client.relationship_partner_id
    ):
        values["relationship_partner_id"] = patch.relationship_partner_id
    if patch.status is not None and patch.status != client.status:
        if not _legal(client.status, patch.status):
            raise IllegalTransition(facts={"client_id": str(client_id)})
        values["status"] = patch.status
    if patch.seen_version != client.version:
        raise StaleVersion(facts={"client_id": str(client_id)})
    if not values:
        return
    async with uow(ctx.tenant) as tx:
        try:
            async with tx.session.begin_nested():
                changed = await tx.session.execute(
                    update(Client)
                    .where(Client.id == client_id, Client.version == patch.seen_version)
                    .values(**values)
                    .returning(Client.version)
                )
                version = changed.scalar_one_or_none()
        except IntegrityError:
            raise ClientRecordInvalid from None  # an office or partner of another firm
        if version is None:
            raise StaleVersion(facts={"client_id": str(client_id)})
        fields = sorted(values)
        tx.record(
            "client.updated",
            target=Target("client", client_id),
            before=Ref(version=patch.seen_version),
            after=Ref(version=version, **dict.fromkeys(fields, 1)),  # names, never values
        )
        tx.emit(ClientUpdated(client_id=client_id, fields=fields))


__all__ = [
    "ClientFilters",
    "ClientPatch",
    "ClientRecordView",
    "ClientRow",
    "IllegalTransition",
    "NewRelationship",
    "StaleVersion",
    "add_relationship",
    "client_overview",
    "client_record",
    "client_relationships",
    "list_clients",
    "update_client",
]
