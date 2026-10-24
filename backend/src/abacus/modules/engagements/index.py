"""ENG-01's engagements index, live (P-07-T15; SPEC-321 AC-16; engagements-v2 contract §3).

Every row, tile, segment and summary figure comes from the same base: engagements the caller may
read the metadata of (`visible(engagement.read_metadata)`, walls included, INV-3), with the
filters applied. Tiles are `counts` per status over the base without the tile, so the selected
tile never shrinks its own count and the seven tiles sum to the header; `declined` is never a row
of the current period and never a tile. Segments are `facets.service_line` over the base without
the service line and the tile. Rows sort by their next deadline, earliest first (past due first),
then by id, on a keyset cursor. A client principal sees nothing here: the index is a firm surface.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Final, Literal, cast
from uuid import UUID

from sqlalchemy import ColumnElement, Date, Select, and_, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel._statuses import EngagementStatus
from abacus.kernel.clock import today
from abacus.kernel.db import tenant_session
from abacus.kernel.errors import NotFound
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
from abacus.modules.engagements.models import Engagement, EngagementLetter, WorkItem
from abacus.modules.identity.api import AuthContext, engagement_team_query, names_of, visible
from abacus.modules.organisations.api import client_name_column, office_name_column

INDEX: Final = "engagements_index"
READ: Final = "engagement.read_metadata"
_FAR: Final = date(9999, 12, 31)
_SOON_DAYS: Final = 7
# A work item's kind names the C2 object its status words come from ("Preparing", "In review").
PILL_OBJECT: Final[dict[str, str | None]] = {
    "tax_return": "return",
    "close": "close",
    "notice": "notice",
    "advisory_project": "project",
    "assurance": None,  # an assurance work item's phase has no status row of its own yet
}
_LETTER_MET: Final = ("signed", "not_required_this_year")
# ENG-01's Partner column: the engagement's partner on its team (identity's team query).
PARTNER_ROLES: Final = ("engagement_partner",)
_ACCEPTED: Final = EngagementStatus.ACCEPTED.value
_BEFORE_LETTER: Final = ("prospect", "declined")
_PAST_PERIOD: Final = ("archived",)


@dataclass(frozen=True)
class IndexFilters:
    service_line: str | None = None
    status: str | None = None
    tile: str | None = None
    office_id: UUID | None = None
    partner_id: UUID | None = None
    letter: Literal["not_signed", "signed"] | None = None
    next_due: Literal["past_due", "within_7_days", "within_30_days"] | None = None
    period: Literal["current", "prior", "all"] = "current"
    client_id: UUID | None = None
    q: str | None = None


@dataclass(frozen=True)
class LetterSummary:
    status: Literal["not_signed", "signed"]
    signed_on: date | None
    signed_count: int
    signer_count: int
    not_required_this_year: bool


@dataclass(frozen=True)
class WorkItemLine:
    id: UUID
    kind: str
    label: str
    pill_object: str | None
    pill_code: str | None


@dataclass(frozen=True)
class NextDue:
    on: date
    tone: Literal["past_due", "soon", "normal"]


@dataclass(frozen=True)
class IndexRow:
    engagement: Engagement
    client_name: str
    office_name: str | None
    partner_user_id: UUID | None
    partner_initials: str | None
    work_items: list[WorkItemLine]
    letter: LetterSummary
    next_due: NextDue | None


@dataclass(frozen=True)
class IndexSummary:
    prospect: int
    awaiting_letter: int
    past_due: int


def _next_due_column() -> ColumnElement[date | None]:
    """The earliest due date of the engagement's open work items."""
    return (
        select(func.min(WorkItem.due_on))
        .where(WorkItem.engagement_id == Engagement.id, WorkItem.archived_at.is_(None))
        .correlate(Engagement)
        .scalar_subquery()
    )


def _letter_met() -> ColumnElement[bool]:
    return (
        select(EngagementLetter.engagement_id)
        .where(
            EngagementLetter.engagement_id == Engagement.id,
            EngagementLetter.status.in_(_LETTER_MET),
        )
        .correlate(Engagement)
        .exists()
    )


def _partner_of(engagement_id: ColumnElement[UUID]) -> ColumnElement[UUID | None]:
    team = engagement_team_query().subquery("team")
    return (
        select(team.c.user_id)
        .where(team.c.engagement_id == engagement_id, team.c.role.in_(PARTNER_ROLES))
        .order_by(team.c.user_id)
        .limit(1)
        .scalar_subquery()
    )


def letter_summary(letter: EngagementLetter | None) -> LetterSummary:
    """The interim recorded letter as ENG-01 and ENG-02 word it (G3 until C7). Signer counts are
    the recorded parties: two when both dates are in."""
    if letter is None or letter.status not in _LETTER_MET:
        signed = (
            0
            if letter is None
            else int(letter.client_signed_on is not None) + int(letter.firm_signed_on is not None)
        )
        return LetterSummary("not_signed", None, signed, 2, False)
    if letter.status == "not_required_this_year":
        return LetterSummary("signed", None, 0, 0, True)
    on = max(
        (d for d in (letter.client_signed_on, letter.firm_signed_on, letter.letter_date) if d),
        default=None,
    )
    return LetterSummary("signed", on, 2, 2, False)


def _next_due(on: date | None, now: date) -> NextDue | None:
    return None if on is None else NextDue(on, tone_of(on, now))


def tone_of(on: date, now: date) -> Literal["past_due", "soon", "normal"]:
    if on < now:
        return "past_due"
    return "soon" if on <= now + timedelta(days=_SOON_DAYS) else "normal"


def _where(
    ctx: AuthContext, f: IndexFilters, now: date, *, tile: bool, service_line: bool
) -> list[Any]:  # Any: SQL boolean clauses
    where: list[Any] = [visible(ctx, READ, Engagement.id)]  # Any: SQL boolean clauses
    if f.period == "current":
        where.append(Engagement.status.not_in((*_PAST_PERIOD, "declined")))
    elif f.period == "prior":
        where.append(Engagement.status.in_(_PAST_PERIOD))
    if service_line and f.service_line is not None:
        where.append(Engagement.service_line == f.service_line)
    if f.status is not None:
        where.append(Engagement.status == f.status)
    if tile and f.tile is not None:
        where.append(Engagement.status == f.tile)
    if f.office_id is not None:
        where.append(Engagement.office_id == f.office_id)
    if f.partner_id is not None:
        where.append(_partner_of(Engagement.id.expression) == f.partner_id)
    if f.client_id is not None:
        where.append(Engagement.client_id == f.client_id)
    if f.letter == "not_signed":
        # "Letter │ Not signed": accepted and beyond without a recorded letter, never a Prospect.
        where.append(and_(Engagement.status.not_in(_BEFORE_LETTER), ~_letter_met()))
    elif f.letter == "signed":
        where.append(_letter_met())
    due = _next_due_column()
    if f.next_due == "past_due":
        where.append(due < now)
    elif f.next_due == "within_7_days":
        where.append(and_(due >= now, due <= now + timedelta(days=7)))
    elif f.next_due == "within_30_days":
        where.append(and_(due >= now, due <= now + timedelta(days=30)))
    if f.q:
        needle = f"%{f.q.strip().lower()}%"
        where.append(
            or_(
                func.lower(Engagement.name).like(needle),
                func.lower(client_name_column(Engagement.client_id)).like(needle),
            )
        )
    return where


async def engagement_index(
    ctx: AuthContext, f: IndexFilters, *, cursor: str | None, limit: int | None
) -> tuple[ListPage[IndexRow], IndexSummary]:
    """ENG-01's rows, tiles, segments and summary over one `visible()` base."""
    if ctx.client:
        raise NotFound("engagements")
    size = clamp_limit(limit)
    digest = query_hash(filters=f.__dict__)  # `q` is hashed, never logged
    after = (
        decode_cursor(cursor, tenant_id=ctx.tenant_id, resource=INDEX, query=digest)
        if cursor
        else None
    )
    now = await today(ctx.tenant)
    sort_key = func.coalesce(_next_due_column(), literal(_FAR, type_=Date()))
    rows_stmt = select(
        Engagement,
        client_name_column(Engagement.client_id).label("client_name"),
        office_name_column(Engagement.office_id).label("office_name"),
        _partner_of(Engagement.id.expression).label("partner_user_id"),
        sort_key.label("sort_key"),
    ).where(*_where(ctx, f, now, tile=True, service_line=True))
    without_tile = select(Engagement.id, Engagement.status).where(
        *_where(ctx, f, now, tile=False, service_line=True)
    )
    for_segments = select(Engagement.id, Engagement.service_line).where(
        *_where(ctx, f, now, tile=False, service_line=False)
    )
    async with tenant_session(ctx.tenant) as session:
        fetched = (
            await session.execute(
                keyset(
                    rows_stmt,
                    sort=cast(ColumnElement[object], sort_key),
                    id_column=cast(ColumnElement[object], Engagement.id.expression),
                    after=after,
                    limit=size,
                )
            )
        ).all()
        page, next_at = page_of(fetched, limit=size, key=lambda r: r[4], id_of=lambda r: r[0].id)
        total = await capped_total(session, cast(Select[Any], rows_stmt))  # Any: counted only
        tiles = cast(Select[Any], without_tile)  # Any: only the status column is read
        counts = await status_counts(session, tiles, Engagement.status.expression)
        counts.pop("declined", None)
        segments = for_segments.subquery("segments")
        lines = await session.execute(
            select(segments.c.service_line, func.count())
            .group_by(segments.c.service_line)
            .order_by(segments.c.service_line)
        )
        facets = {"service_line": [Facet(value=s, label=s, n=int(n)) for s, n in lines.all()]}
        summary = await _summary(session, cast(Select[Any], without_tile), now)  # Any: re-selected
        ids = [r[0].id for r in page]
        work = await _work_item_lines(session, ids)
        letters = {
            letter.engagement_id: letter
            for letter in (
                await session.execute(
                    select(EngagementLetter).where(EngagementLetter.engagement_id.in_(ids))
                )
            ).scalars()
        }
        dues = dict(
            (
                await session.execute(
                    select(WorkItem.engagement_id, func.min(WorkItem.due_on))
                    .where(WorkItem.engagement_id.in_(ids), WorkItem.archived_at.is_(None))
                    .group_by(WorkItem.engagement_id)
                )
            )
            .tuples()
            .all()
        )
    partners = {cast(UUID, r[3]) for r in page if r[3] is not None}
    initials = (
        {uid: _initials(name) for uid, name in (await names_of(sorted(partners))).items()}
        if partners
        else {}
    )
    items = [
        IndexRow(
            engagement=e,
            client_name=client_name,
            office_name=office_name,
            partner_user_id=partner,
            partner_initials=initials.get(partner) if partner else None,
            work_items=work.get(e.id, []),
            letter=letter_summary(letters.get(e.id)),
            next_due=_next_due(dues.get(e.id), now),
        )
        for e, client_name, office_name, partner, _key in page
    ]
    found = envelope(
        items,
        next_position=next_at,
        tenant_id=ctx.tenant_id,
        resource=INDEX,
        query=digest,
        total=total,
        counts=counts,
        facets=facets,
    )
    return found, summary


async def _summary(
    session: AsyncSession,
    base: Select[Any],  # Any: re-selected with the summary's own columns
    now: date,
) -> IndexSummary:
    """Prospects, Accepted without a recorded letter, and past due, over the tiles' base."""
    rows = base.with_only_columns(
        Engagement.status,
        _letter_met().label("letter_met"),
        _next_due_column().label("due"),
    ).subquery("summary_rows")
    found = (
        await session.execute(
            select(
                func.count().filter(rows.c.status == "prospect"),
                func.count().filter(and_(rows.c.status == _ACCEPTED, ~rows.c.letter_met)),
                func.count().filter(rows.c.due < now),
            )
        )
    ).one()
    return IndexSummary(int(found[0]), int(found[1]), int(found[2]))


async def _work_item_lines(
    session: AsyncSession, ids: list[UUID]
) -> dict[UUID, list[WorkItemLine]]:
    """Each engagement's open work items as sub-lines, in their kind's own status words."""
    if not ids:
        return {}
    rows = await session.execute(
        select(WorkItem.engagement_id, WorkItem.id, WorkItem.kind, WorkItem.name, WorkItem.status)
        .where(WorkItem.engagement_id.in_(ids), WorkItem.archived_at.is_(None))
        .order_by(WorkItem.engagement_id, WorkItem.name, WorkItem.id)
    )
    out: dict[UUID, list[WorkItemLine]] = {}
    for engagement_id, wid, kind, name, status in rows.all():
        pill = PILL_OBJECT.get(kind)
        out.setdefault(engagement_id, []).append(
            WorkItemLine(wid, kind, name, pill, status if pill else None)
        )
    return out


def _initials(name: str) -> str:
    return "".join(part[0] for part in name.split() if part[:1].isalpha())[:3].upper()
