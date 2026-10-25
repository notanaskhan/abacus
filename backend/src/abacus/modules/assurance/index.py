"""AUD-01's audits index, live (A-01-T08; SPEC-330 AC-18 to AC-21; DEC-311;
docs/contracts/audits-cockpit.md §3).

Every row, tile, segment, facet and caption figure comes from one base: the firm's engaged
assurance work items whose engagement the reader may read the metadata of
(`visible(engagement.read_metadata)`, walls included, INV-3), with the filters applied.

- **Tiles** are `counts` per phase over the base without the phase tile, so the pressed tile
  keeps its count and, with no tile pressed, the tiles sum to `total`. Archived rows group under
  Released (DEC-263): the row's phase reads `released` and its Archive cell `archived`.
- **Segments** (`facets.segment`) are counted over the base without the segment filter, for the
  registered segments the firm is entitled to (X-01 and X-03 add theirs). The **caption**
  (`summary`) counts the tile base by family.
- **Rows** sort in tile order, then by report due (none last), then by name, on a keyset cursor
  sealed to the firm and the query (a name never sits readable in a URL).
- **PBC** is `requests.api.pbc_counts` (null before a published PBC binder, DEC-39); **report
  due** is the work item's due date (DV-6) with its tone on `kernel.clock` (DEC-263); the
  **archive clock** counts 60 days from the day the phase became Released (until A-01-T23's
  external release record carries the report date).
- **Tags** come only from registered providers (DV-10); a `content` provider's tags reach only a
  reader who may also read the engagement's content (ADR-024), a `metadata` one's every reader.
- **Run badge** only from a registered C6 v1 engagement-run provider (DV-11).

No field counts a hidden row; nothing here carries an amount or a materiality.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from typing import Any, Final, cast
from uuid import UUID

from sqlalchemy import ColumnElement, Row, Select, String, case, func, literal, or_, select
from sqlalchemy import cast as sql_cast

from abacus.kernel.clock import FIRM_ZONE, today
from abacus.kernel.db import tenant_session
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
)
from abacus.kernel.logging import get_logger
from abacus.modules.assurance.sections import (
    IndexTag,
    RunSummary,
    registered_index_tags,
    registered_segments,
    run_summaries,
)
from abacus.modules.engagements.api import assurance_index
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    engagement_team_query,
    names_of,
    visible,
)
from abacus.modules.platform.api import entitlement
from abacus.modules.requests.api import pbc_counts

INDEX: Final = "audits_index"
READ: Final = "engagement.read_metadata"
CONTENT: Final = "engagement.read"
# AUD-01's tile order (DV-12: Completion has no tile until DF-05; it is never offered).
TILES: Final = ("planning", "fieldwork", "in_review", "completion", "ready_to_release", "released")
ARCHIVE_DAYS: Final = 60  # G9: archive within 60 days of release (blueprint §3.3.2)
_FAR: Final = "9999-12-31"
WINDOWS: Final = {"7d": 7, "14d": 14, "30d": 30}
_EBP: Final = "ebp_audit"
_SOC: Final = ("soc1", "soc2", "readiness")
_REVIEW: Final = ("review",)
_COMPILATION: Final = ("compilation", "preparation")
# AUD-01's "EP / Mgr" column: who holds these team roles (a column, not a permission).
PARTNER_ROLES: Final = ("engagement_partner",)
LEAD_ROLES: Final = ("engagement_partner", "manager")
_log = get_logger(__name__)


@dataclass(frozen=True)
class IndexFilters:
    segment: str | None = None
    type: str | None = None
    phase: str | None = None  # the tile
    partner: UUID | None = None
    office: UUID | None = None
    due: str = "any"
    period: str | None = None
    q: str | None = None


@dataclass(frozen=True)
class Pbc:
    received: int
    total: int


@dataclass(frozen=True)
class Archive:
    state: str
    days_left: int | None = None
    firm_tool_ref: str | None = None


@dataclass(frozen=True)
class TagView:
    source: str
    code: str
    text: str
    classification: str


@dataclass(frozen=True)
class IndexRow:
    work_item_id: UUID
    engagement_id: UUID
    client_id: UUID
    client_name: str
    name: str
    engagement_type: str
    segment: str
    ebp_plan_kind: str | None
    limited_scope_103a3c: bool
    is_group_audit: bool
    period_label: str | None
    phase: str
    released_on: date | None
    run_badge: RunSummary | None
    tags: list[TagView]
    pbc: Pbc | None
    partner_initials: str | None
    manager_initials: str | None
    office_id: UUID | None
    office_name: str | None
    report_due_on: date | None
    report_due_tone: str | None
    archive: Archive | None
    allowed_actions: list[str]


@dataclass(frozen=True)
class Summary:
    ebp: int
    fs_audit: int
    review: int
    compilation_preparation: int
    soc: int
    internal_audit: int


def initials(name: str) -> str:
    """ "Margaret Okonkwo" → "MO"."""
    return "".join(part[0] for part in name.split() if part[:1].isalpha())[:3].upper()


def like_escaped(text: str) -> str:
    """`q` as a literal substring: LIKE's wildcards and its escape character escaped."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def tile_of(phase: ColumnElement[str]) -> ColumnElement[str]:
    """The tile a phase counts under: an archived row groups under Released (DEC-263)."""
    return case((phase.in_(("archiving", "archived")), literal("released")), else_=phase)


def segment_of(kind: ColumnElement[str], plan: ColumnElement[str | None]) -> ColumnElement[str]:
    return case(
        ((kind == _EBP) | plan.is_not(None), literal("ebp")),
        (kind == "fs_audit", literal("fs")),
        (kind.in_(_SOC), literal("soc")),
        (kind == "internal_audit", literal("ia")),
        else_=literal("review"),
    )


def due_tone(due: date | None, now: date) -> str | None:
    """DEC-263: fewer than 7 days left is red, 7 to 30 amber, beyond later; before today past."""
    if due is None:
        return None
    left = (due - now).days
    if left < 0:
        return "past_due"
    if left < 7:
        return "within_7_days"
    if left <= 30:
        return "within_30_days"
    return "later"


def _partner_of(engagement_id: ColumnElement[UUID]) -> ColumnElement[UUID | None]:
    team = engagement_team_query().subquery("partner_team")
    return (
        select(team.c.user_id)
        .where(team.c.engagement_id == engagement_id, team.c.role.in_(PARTNER_ROLES))
        .order_by(team.c.user_id)
        .limit(1)
        .scalar_subquery()
    )


async def _entitled(ctx: AuthContext) -> frozenset[str]:
    held: set[str] = set()
    for module in ("attest", "internal_audit"):
        if await entitlement(ctx.tenant, module) is not None:
            held.add(module)
    return frozenset(held)


async def audits_index(
    ctx: AuthContext, f: IndexFilters, *, cursor: str | None, limit: int | None
) -> tuple[ListPage[IndexRow], Summary]:
    """AUD-01's rows, tiles, segments, facets and caption over one `visible()` base. The route has
    refused client principals, agents and the system (INV-4); so does this read model itself,
    since client principals hold `engagement.read_metadata` cells (security review, DEC-311)."""
    if ctx.client or ctx.tenant.actor_kind != "human":
        raise Forbidden(READ, "role")
    size = clamp_limit(limit)
    digest = query_hash(filters=asdict(f))  # `q` is hashed, never logged
    after = (
        decode_cursor(cursor, tenant_id=ctx.tenant_id, resource=INDEX, query=digest)
        if cursor
        else None
    )
    now = await today(ctx.tenant)
    a = assurance_index()
    tile = tile_of(a.c.phase)
    segment = segment_of(a.c.type, a.c.ebp_plan_kind)
    entitled = await _entitled(ctx)
    shown = tuple(s.family for s in registered_segments(entitled))

    def where(*, with_tile: bool, with_segment: bool) -> list[Any]:  # Any: SQL clauses
        clauses: list[Any] = [  # Any: SQL clauses
            visible(ctx, READ, a.c.engagement_id),
            segment.in_(shown),
        ]
        if with_segment and f.segment is not None:
            clauses.append(segment == f.segment)
        if with_tile and f.phase is not None:
            clauses.append(tile == tile_of(literal(f.phase)))
        if f.type is not None:
            clauses.append(a.c.type == f.type)
        if f.partner is not None:
            clauses.append(_partner_of(a.c.engagement_id) == f.partner)
        if f.office is not None:
            clauses.append(a.c.office_id == f.office)
        if f.due in WINDOWS:
            clauses.append(a.c.due_on.between(now, now + timedelta(days=WINDOWS[f.due])))
        if f.period is not None:
            clauses.append(a.c.period_label == f.period)
        if f.q and f.q.strip():
            needle = f"%{like_escaped(f.q.strip().lower())}%"
            clauses.append(
                or_(
                    func.lower(a.c.name).like(needle, escape="\\"),
                    func.lower(a.c.client_name).like(needle, escape="\\"),
                )
            )
        return clauses

    rank = case(*((tile == t, literal(n)) for n, t in enumerate(TILES)), else_=literal(len(TILES)))
    sort_key = func.concat(
        sql_cast(rank, String),
        "|",
        func.coalesce(func.to_char(a.c.due_on, "YYYY-MM-DD"), _FAR),
        "|",
        func.lower(a.c.name),
    )
    rows_stmt = select(a, sort_key.label("sort_key")).where(
        *where(with_tile=True, with_segment=True)
    )
    tile_base = select(a.c.work_item_id, tile.label("tile"), segment.label("segment"), a.c.type)
    tile_base = tile_base.where(*where(with_tile=False, with_segment=True))
    segment_base = select(a.c.work_item_id, segment.label("segment")).where(
        *where(with_tile=True, with_segment=False)
    )
    async with tenant_session(ctx.tenant) as session:
        fetched = (
            await session.execute(
                keyset(
                    rows_stmt,
                    sort=cast(ColumnElement[object], sort_key),
                    id_column=cast(ColumnElement[object], a.c.work_item_id),
                    after=after,
                    limit=size,
                )
            )
        ).all()
        page, next_at = page_of(
            fetched, limit=size, key=lambda r: r.sort_key, id_of=lambda r: r.work_item_id
        )
        total = await capped_total(session, cast(Select[Any], rows_stmt))  # Any: counted only
        tb = tile_base.subquery("tiles")
        counted = await session.execute(
            select(tb.c.tile, tb.c.segment, tb.c.type, func.count()).group_by(
                tb.c.tile, tb.c.segment, tb.c.type
            )
        )
        groups = [(str(t), str(s), str(k), int(n)) for t, s, k, n in counted.all()]
        sb = segment_base.subquery("segments")
        by_segment = {
            str(seg): int(n)
            for seg, n in (
                await session.execute(select(sb.c.segment, func.count()).group_by(sb.c.segment))
            ).all()
        }
        page_engagements = [r.engagement_id for r in page]
        readable: set[UUID] = set()
        if page_engagements:
            readable = set(
                (
                    await session.execute(
                        select(a.c.engagement_id).where(
                            a.c.engagement_id.in_(page_engagements),
                            visible(ctx, CONTENT, a.c.engagement_id),
                        )
                    )
                ).scalars()
            )
        team = engagement_team_query().subquery("team")
        members: Sequence[Row[Any, Any, Any]] = (  # Any: (engagement, user, role)
            (
                await session.execute(
                    select(team.c.engagement_id, team.c.user_id, team.c.role)
                    .where(team.c.engagement_id.in_(page_engagements))
                    .order_by(team.c.engagement_id, team.c.role, team.c.user_id)
                )
            ).all()
            if page_engagements
            else []
        )
    counts: dict[str, int] = {}
    for t, _, _, n in groups:
        counts[t] = counts.get(t, 0) + n
    summary = Summary(
        ebp=sum(n for _, s, _, n in groups if s == "ebp"),
        fs_audit=sum(n for _, s, _, n in groups if s == "fs"),
        review=sum(n for _, s, k, n in groups if s == "review" and k in _REVIEW),
        compilation_preparation=sum(
            n for _, s, k, n in groups if s == "review" and k in _COMPILATION
        ),
        soc=sum(n for _, s, _, n in groups if s == "soc"),
        internal_audit=sum(n for _, s, _, n in groups if s == "ia"),
    )
    facets = {
        "segment": [Facet(value=s, label=s, n=int(by_segment.get(s, 0))) for s in shown],
        "type": [
            Facet(value=k, label=k, n=n)
            for k, n in sorted(_sum_by(groups, lambda g: g[2]).items())
        ],
    }
    people = sorted({m.user_id for m in members})
    names = await names_of(people) if people else {}
    leads: dict[UUID, dict[str, str]] = {}
    for m in members:
        if m.role in LEAD_ROLES and m.user_id in names:
            leads.setdefault(m.engagement_id, {}).setdefault(m.role, initials(names[m.user_id]))
    ids = [r.work_item_id for r in page]
    pbc = await pbc_counts(ctx, ids)
    # The run badge is content (a run's progress): only rows the reader may read in content.
    runs = await run_summaries(
        ctx.tenant, [r.work_item_id for r in page if r.engagement_id in readable]
    )
    tags = await _tags(ctx, page, readable)
    items = [
        _row(r, now, leads.get(r.engagement_id, {}), pbc.get(r.work_item_id), runs, tags)
        for r in page
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


def _sum_by(
    groups: list[tuple[str, str, str, int]],
    key: Callable[[tuple[str, str, str, int]], str],
) -> dict[str, int]:
    out: dict[str, int] = {}
    for g in groups:
        k = key(g)
        out[k] = out.get(k, 0) + g[3]
    return out


async def _tags(
    ctx: AuthContext,
    page: list[Row[Any]],  # Any: the assurance index's columns
    readable: set[UUID],
) -> dict[UUID, list[TagView]]:
    """Each row's tags from the registered providers, `content` ones only where the reader may
    read the engagement's content (ADR-024). A failing provider shows no tags (never a guess)."""
    out: dict[UUID, list[TagView]] = {}
    ids = [r.work_item_id for r in page]
    if not ids:
        return out
    content_ok = {r.work_item_id for r in page if r.engagement_id in readable}
    for source in registered_index_tags(metadata_only=False):
        allowed = (
            ids if source.classification == "metadata" else [i for i in ids if i in content_ok]
        )
        if not allowed:
            continue
        try:
            found = await source.provider(ctx.tenant, allowed)
        except Exception:  # a failing provider's tags are left out, never the row
            _log.warning("audits.index_tag_failed", source=source.name)
            continue
        for wid in allowed:
            for tag in found.get(wid, ()):
                out.setdefault(wid, []).append(_tag(source.name, tag, source.classification))
    return out


def _tag(source: str, tag: IndexTag, classification: str) -> TagView:
    return TagView(source, tag.code, tag.text, classification)


def _row(
    r: Row[Any],  # Any: the assurance index's columns
    now: date,
    leads: dict[str, str],
    pbc: tuple[int, int] | None,
    runs: Mapping[UUID, RunSummary],
    tags: dict[UUID, list[TagView]],
) -> IndexRow:
    archived = (
        r.archived_at is not None
        or r.archive_locked_at is not None
        or r.phase == "archived"
        or r.status == "archived"
        or r.work_item_status == "archived"
    )
    phase = "released" if r.phase in ("archiving", "archived") else r.phase
    released_on = (
        r.phase_changed_at.astimezone(FIRM_ZONE).date()
        if r.phase == "released" and r.phase_changed_at is not None
        else None
    )
    archive: Archive | None = None
    if archived:
        archive = Archive("archived")
    elif released_on is not None:
        archive = Archive("archiving", (released_on + timedelta(days=ARCHIVE_DAYS) - now).days)
    return IndexRow(
        work_item_id=r.work_item_id,
        engagement_id=r.engagement_id,
        client_id=r.client_id,
        client_name=r.client_name,
        name=r.name,
        engagement_type=r.type,
        segment=_segment(r.type, r.ebp_plan_kind),
        ebp_plan_kind=r.ebp_plan_kind,
        limited_scope_103a3c=bool(r.limited_scope_103a3c),
        is_group_audit=bool(r.is_group_audit),
        period_label=r.period_label,
        phase=phase,
        released_on=released_on,
        run_badge=runs.get(r.work_item_id),
        tags=tags.get(r.work_item_id, []),
        pbc=Pbc(*pbc) if pbc is not None else None,
        partner_initials=leads.get("engagement_partner"),
        manager_initials=leads.get("manager"),
        office_id=r.office_id,
        office_name=r.office_name,
        report_due_on=r.due_on,
        report_due_tone=due_tone(r.due_on, now),
        archive=archive,
        allowed_actions=[],
    )


def _segment(kind: str, plan: str | None) -> str:
    if kind == _EBP or plan is not None:
        return "ebp"
    if kind == "fs_audit":
        return "fs"
    if kind in _SOC:
        return "soc"
    if kind == "internal_audit":
        return "ia"
    return "review"
