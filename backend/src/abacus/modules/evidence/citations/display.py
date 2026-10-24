"""Reading citations: the display contract SHL-07 and SHL-08 read (P-03-T08; C4 §3.2; ADR-166;
DEC-265). PROTECTED.

`citation_display` answers one citation, `citation_list` an anchor's stack, a host's section, the
rows citing one evidence version, or a kind. Rules:
- **Who:** a client principal is refused before anything is read (INV-4: 403). One citation is
  authorised with `citation.read` on its engagement (a wall answers 404, DEC-43); a list filters
  through `visible(citation.read)`, so a walled citation is omitted with no hidden count (INV-3).
  A citation with no engagement (a firm-level anchor) takes its visibility from its anchor's
  provider; none is registered before P-04, so it is never served.
- **Rendered by code:** `title` and `loc` come from the kind's registered display function, from
  the stored locator, never from model text (INV-2); a kind with no display, or an unverified
  citation (whose source may not be in its engagement), reads its kind and names no file.
- **The quote is never stored:** it is re-read from the word layer inside the stored box, kept
  only when its words hash to the stored `quote_sha256` (`shown`), and returned from the masked
  projection. No run hashing to it is `changed`, and the citation is then reported unverified
  (`quote_not_found`): what the layer holds no longer supports it. An unreadable layer
  (crypto-shredded), a quote with no box, or a page no PII scan covers (fail closed: none is
  scanned before P-03-T13) is `withheld`. A shown quote is a content read: an
  `evidence_content.read` access event is written for its source before the answer leaves.
- **State is computed** from `citation_events`: `relinked` once relinked, else the latest of
  `moved` and `broken`, else `valid`. A citation is never updated.
- **`used_in`** counts the distinct anchors, visible to the reader, citing the same `match_id`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Final, cast
from uuid import UUID

from sqlalchemy import ColumnElement, Select, distinct, func, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.listing import (
    ListPage,
    capped_total,
    clamp_limit,
    decode_cursor,
    envelope,
    keyset,
    page_of,
    query_hash,
)
from abacus.modules.engagements.api import get_ref
from abacus.modules.evidence.access import record_content_read
from abacus.modules.evidence.citations.matching import reread_span
from abacus.modules.evidence.citations.registry import citable
from abacus.modules.evidence.models import Citation, CitationEvent, EvidencePage
from abacus.modules.evidence.projection import Projection, projection_of
from abacus.modules.evidence.repository import events_of, get_citation, pages_of
from abacus.modules.evidence.words import WORDS_VERSION, read_page_layer
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    Resource,
    allowed_actions,
    authorise,
    names_of,
    visible,
)

READ: Final = "citation.read"
# A citation's engagement; null for a firm-level anchor, which `visible()` never admits.
_ENGAGEMENT: Final = cast(ColumnElement[UUID], Citation.engagement_id.expression)
RELINK: Final = "citation.relink"
RESOURCE: Final = "citations"
_KIND_TITLES: Final = {
    "document_text": "Document",
    "sheet_cell": "Spreadsheet",
    "ledger_line": "Ledger line",
    "workpaper_cell": "Workpaper cell",
    "methodology_step": "Methodology step",
    "policy_rule": "Policy rule",
    "record_field": "Record field",
    "tax_form_line": "Tax form line",
    "artifact_cell": "Artifact cell",
    "request_item": "Request item",
}


@dataclass(frozen=True)
class CreatorView:
    kind: str
    label: str


@dataclass(frozen=True)
class SourceView:
    type: str
    id: UUID
    version: str | None
    evidence_version_id: UUID | None
    page: int | None


@dataclass(frozen=True)
class MovedView:
    successor_ref: str | None
    at: datetime


@dataclass(frozen=True)
class CitationView:
    id: UUID
    n: int
    kind: str
    title: str
    loc: str
    quote: str | None
    quote_state: str
    value_text: str | None
    match_id: str | None
    state: str
    verified: bool
    verification_reason: str | None
    created_by: CreatorView
    retrieved_at: datetime | None
    source: SourceView
    used_in: int
    moved: MovedView | None
    allowed_actions: list[str] = field(default_factory=list[str])


@dataclass(frozen=True)
class CitationFilters:
    anchor_type: str | None = None
    anchor_id: UUID | None = None
    anchor_ref: str | None = None
    host_ref: str | None = None  # `<anchor_type>:<anchor_id>` (DEC-265)
    section_id: str | None = None
    source_version_id: UUID | None = None
    kind: str | None = None


def _refuse_clients(ctx: AuthContext) -> None:
    """Clients never read citations (INV-4; C4 §6: 403 on every citation route)."""
    if ctx.client:
        raise Forbidden(READ, "role")


def host_of(host_ref: str) -> tuple[str, UUID] | None:
    """`<anchor_type>:<anchor_id>` as its parts, or None when it isn't one."""
    kind, _, raw = host_ref.partition(":")
    if not kind or not raw:
        return None
    try:
        return kind, UUID(raw)
    except ValueError:
        return None


# --- one row's display -------------------------------------------------------------------------


def state_of(events: Sequence[CitationEvent]) -> tuple[str, CitationEvent | None]:
    """The computed state and, when moved, the event that moved it (events oldest first)."""
    if any(e.kind == "relinked" for e in events):
        return "relinked", None
    latest = next((e for e in reversed(events) if e.kind in ("moved", "broken")), None)
    if latest is None:
        return "valid", None
    return latest.kind, latest if latest.kind == "moved" else None


def _box(raw: object) -> tuple[float, float, float, float] | None:
    if not isinstance(raw, list) or len(cast(list[object], raw)) != 4:
        return None
    try:
        values = [float(cast(float, v)) for v in cast(list[object], raw)]
    except (TypeError, ValueError):
        return None
    return (values[0], values[1], values[2], values[3])


def _page_no(locator: dict[str, object]) -> int | None:
    raw = locator.get("page")
    return raw if isinstance(raw, int) and not isinstance(raw, bool) else None


def _source_ids(row: Citation) -> tuple[UUID | None, UUID | None]:
    if row.source_type == "evidence_version":
        return row.source_id, None
    if row.source_type == "inbox_file":
        return None, row.source_id
    return None, None


@dataclass
class _Reads:
    """What one request has read already: a source's pages and its masked projection are read
    once however often it's cited."""

    pages: dict[tuple[UUID | None, UUID | None], Sequence[EvidencePage]] = field(
        default_factory=dict[tuple[UUID | None, UUID | None], Sequence[EvidencePage]]
    )
    projections: dict[tuple[UUID | None, UUID | None], Projection] = field(
        default_factory=dict[tuple[UUID | None, UUID | None], Projection]
    )


async def _quote(
    session: AsyncSession, tenant_id: UUID, row: Citation, reads: _Reads
) -> tuple[str | None, str]:
    """The re-read quote and its state (shown, withheld, changed). A page no PII scan covers is
    `withheld`, never quoted raw (fail closed, `projection`)."""
    if row.quote_sha256 is None:
        return None, "shown"  # nothing was quoted
    box, page_no = _box(row.locator.get("bbox")), _page_no(row.locator)
    key = _source_ids(row)
    if row.kind != "document_text" or box is None or page_no is None or key == (None, None):
        return None, "withheld"  # no region to re-read (verified on page text, AC-3)
    if key not in reads.pages:
        reads.pages[key] = await pages_of(
            session,
            evidence_version_id=key[0],
            inbox_file_id=key[1],
            extractor_version=WORDS_VERSION,
        )
        reads.projections[key] = await projection_of(
            session, evidence_version_id=key[0], inbox_file_id=key[1]
        )
    page = next((p for p in reads.pages[key] if p.page_no == page_no), None)
    if page is None or not page.has_text_layer:
        return None, "withheld"
    try:
        layer = await read_page_layer(tenant_id, page)
    except Exception:  # a shredded or unreadable layer object: storage raises several kinds
        return None, "withheld"
    run = reread_span(layer.words, box, row.quote_sha256)
    if run is None:
        return None, "changed"
    words = reads.projections[key].words(run, page_no)
    if words is None:
        return None, "withheld"  # not scanned for PII: never quoted raw
    return " ".join(w.text for w in words), "shown"


async def _used_in(
    session: AsyncSession, ctx: AuthContext, match_ids: Sequence[str]
) -> dict[str, int]:
    """Distinct anchors, visible to the reader, citing each match (no hidden count)."""
    if not match_ids:
        return {}
    rows = await session.execute(
        select(
            Citation.match_id,
            func.count(distinct(tuple_(Citation.cited_from_type, Citation.cited_from_id))),
        )
        .where(Citation.match_id.in_(list(match_ids)), visible(ctx, READ, _ENGAGEMENT))
        .group_by(Citation.match_id)
    )
    return {str(m): int(n) for m, n in rows.all()}


def _creator(row: Citation, names: dict[UUID, str]) -> CreatorView:
    """Attributed by code (INV-5): "<person> via Agent" for an agent row."""
    if row.created_by_kind == "agent":
        person = names.get(row.on_behalf_of_user_id) if row.on_behalf_of_user_id else None
        return CreatorView("agent", f"{person} via Agent" if person else "Accrued Agent")
    if row.created_by_kind == "human":
        person = names.get(row.created_by_user_id) if row.created_by_user_id else None
        return CreatorView("human", person or "Former member")
    return CreatorView("system", "Accrued")


async def _views(
    session: AsyncSession,
    ctx: AuthContext,
    rows: Sequence[Citation],
    resources: dict[UUID, Resource],
) -> list[CitationView]:
    reads = _Reads()
    events = await events_of(session, [r.id for r in rows])
    by_citation: dict[UUID, list[CitationEvent]] = {}
    for event in events:
        by_citation.setdefault(event.citation_id, []).append(event)
    used = await _used_in(session, ctx, sorted({r.match_id for r in rows if r.match_id}))
    people = {
        u for r in rows for u in (r.on_behalf_of_user_id, r.created_by_user_id) if u is not None
    }
    names = await names_of(sorted(people)) if people else {}
    relink: dict[UUID, bool] = {}
    read: set[tuple[UUID, str, UUID]] = set()  # sources whose text a quote shows
    out: list[CitationView] = []
    for row in rows:
        state, moved = state_of(by_citation.get(row.id, []))
        registered = citable(row.kind)
        if registered is not None and row.verified:
            # Only a verified row's source is known to be in its engagement; the display
            # function checks that again before naming the file (security review #3).
            shown = await registered.display(session, row.locator, row.engagement_id)
            title, loc = shown.title, shown.loc
        else:
            title, loc = _KIND_TITLES.get(row.kind, "Source"), ""
        quote, quote_state = await _quote(session, ctx.tenant_id, row, reads)
        verified, reason = row.verified, row.verification_reason
        if quote_state == "changed":
            verified, reason = False, "quote_not_found"  # never shown as fact (INV-2)
        actions: list[str] = []
        if state == "moved" and row.engagement_id is not None:
            if row.engagement_id not in relink:
                held = await allowed_actions(ctx, resources[row.engagement_id], [RELINK])
                relink[row.engagement_id] = RELINK in held
            if relink[row.engagement_id]:
                actions.append(RELINK)
        version_id, inbox_id = _source_ids(row)
        if quote is not None and row.engagement_id is not None:
            subject = ("evidence_version", version_id) if version_id else ("inbox_file", inbox_id)
            if subject[1] is not None:
                read.add((row.engagement_id, subject[0], subject[1]))
        out.append(
            CitationView(
                id=row.id,
                n=row.n,
                kind=row.kind,
                title=title,
                loc=loc,
                quote=quote,
                quote_state=quote_state,
                value_text=row.value_text if verified else None,
                match_id=row.match_id,
                state=state,
                verified=verified,
                verification_reason=reason,
                created_by=_creator(row, names),
                retrieved_at=row.created_at,
                source=SourceView(
                    row.source_type,
                    row.source_id,
                    row.source_version,
                    version_id,
                    _page_no(row.locator),
                ),
                used_in=used.get(row.match_id, 1) if row.match_id else 1,
                moved=MovedView(moved.cause_ref, moved.at) if moved is not None else None,
                allowed_actions=actions,
            )
        )
    # A re-read quote is client content (Restricted): its read is logged before it is answered,
    # and nothing is answered if logging fails (Q-02-T20; security review #2).
    for engagement_id, subject_type, subject_id in sorted(read, key=str):
        await record_content_read(ctx, engagement_id, subject_type, subject_id)
    return out


# --- the routes' reads -------------------------------------------------------------------------


async def citation_display(ctx: AuthContext, citation_id: UUID) -> CitationView:
    """One citation for a person who may read it on its engagement (404 when walled, unknown or
    firm-level; 403 for a client or a role without `citation.read`)."""
    _refuse_clients(ctx)
    async with tenant_session(ctx.tenant) as session:
        row = await get_citation(session, citation_id)
    if row is None or row.engagement_id is None:
        raise NotFound("citation")
    engagement = await get_ref(ctx, row.engagement_id)
    resource = engagement.resource()
    await authorise(ctx, READ, resource)
    async with tenant_session(ctx.tenant) as session:
        [view] = await _views(session, ctx, [row], {row.engagement_id: resource})
    return view


def _filtered(ctx: AuthContext, filters: CitationFilters) -> Select[Citation] | None:
    stmt = select(Citation).where(visible(ctx, READ, _ENGAGEMENT))
    if filters.anchor_type is not None:
        stmt = stmt.where(Citation.cited_from_type == filters.anchor_type)
    if filters.anchor_id is not None:
        stmt = stmt.where(Citation.cited_from_id == filters.anchor_id)
    if filters.anchor_ref is not None:
        stmt = stmt.where(Citation.cited_from_ref == filters.anchor_ref)
    if filters.host_ref is not None:
        host = host_of(filters.host_ref)
        if host is None:
            return None
        stmt = stmt.where(Citation.cited_from_type == host[0], Citation.cited_from_id == host[1])
    if filters.section_id is not None:
        stmt = stmt.where(Citation.cited_from_locator["section_id"].astext == filters.section_id)
    if filters.source_version_id is not None:
        stmt = stmt.where(
            Citation.source_type == "evidence_version",
            Citation.source_id == filters.source_version_id,
        )
    if filters.kind is not None:
        stmt = stmt.where(Citation.kind == filters.kind)
    return stmt


async def citation_list(
    ctx: AuthContext, filters: CitationFilters, *, cursor: str | None, limit: int | None
) -> ListPage[CitationView]:
    """The citations the reader may see, through `visible()`: an anchor's stack by `n`, else
    oldest first. A walled citation is left out and counted nowhere."""
    _refuse_clients(ctx)
    size = clamp_limit(limit)
    query = query_hash(**{k: str(v) for k, v in vars(filters).items() if v is not None})
    after = (
        decode_cursor(cursor, tenant_id=ctx.tenant_id, resource=RESOURCE, query=query)
        if cursor
        else None
    )
    stack = filters.anchor_id is not None or filters.host_ref is not None
    stmt = _filtered(ctx, filters)
    if stmt is None:
        return envelope(
            [],
            next_position=None,
            tenant_id=ctx.tenant_id,
            resource=RESOURCE,
            query=query,
            total=(0, False),
        )
    sort = cast(ColumnElement[object], (Citation.n if stack else Citation.created_at).expression)
    async with tenant_session(ctx.tenant) as session:
        total = await capped_total(session, stmt)
        fetched: Sequence[Citation] = (
            (
                await session.execute(
                    keyset(
                        stmt,
                        sort=sort,
                        id_column=cast(ColumnElement[object], Citation.id.expression),
                        after=after,
                        limit=size,
                    )
                )
            )
            .scalars()
            .all()
        )

        def key(row: Citation) -> object:
            return row.n if stack else row.created_at

        rows, position = page_of(fetched, limit=size, key=key, id_of=lambda r: r.id)
        resources: dict[UUID, Resource] = {}
        for engagement_id in sorted({r.engagement_id for r in rows if r.engagement_id}):
            resources[engagement_id] = (await get_ref(ctx, engagement_id)).resource()
        views = await _views(session, ctx, rows, resources)
    return envelope(
        views,
        next_position=position,
        tenant_id=ctx.tenant_id,
        resource=RESOURCE,
        query=query,
        total=total,
    )


__all__ = [
    "CitationFilters",
    "CitationView",
    "CreatorView",
    "MovedView",
    "SourceView",
    "citation_display",
    "citation_list",
    "host_of",
    "state_of",
]
