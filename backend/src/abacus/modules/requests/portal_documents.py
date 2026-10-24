"""R-01-T07: what the portal PBC read model reads of binders and requests (C5 section
`portal-pbc`; POR-03, POR-04). The portal composes it with evidence's files and the client words;
this module answers the requests' own facts only.

What a client reads (INV-4): a binder once it is published (or marked done, or closed after it was
published: read-only); of it, the client-visible requests `visible_items` gives them (a client
admin's grant reads every client-visible one, a contributor's only those assigned to them), and
never a draft, a deleted request or one delegated to a third party. A delegated request goes to
its third party directly: only the delegates' contacts are returned, so the portal can name their
organisations to a client admin. Live fulfilments only: a withdrawn upload is as if it never
arrived (ADR-162 §4). The caller authorises `portal_documents.read` on the binder's work item.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.db import tenant_session
from abacus.modules.identity.api import AuthContext, drafted_guidance_to_clients
from abacus.modules.requests.binders import firm_acted_since
from abacus.modules.requests.guidance import for_client
from abacus.modules.requests.models import RequestItem, RequestList
from abacus.modules.requests.repository import (
    binder_categories,
    binder_delegated_contacts,
    binder_items,
    client_responses,
    list_comment_counts,
    live_links,
    live_upload_intents,
    portal_binder,
    portal_binders,
    portal_item,
    portal_items,
    prior_year_item,
)


@dataclass(frozen=True)
class PortalLink:
    """A live fulfilment: which version, and who linked it (`human`, `rule`, `agent`, …)."""

    fulfilment_id: UUID
    evidence_version_id: UUID
    created_by_kind: str
    created_at: datetime


@dataclass(frozen=True)
class PortalCategory:
    id: UUID
    name: str
    position: int


@dataclass(frozen=True)
class PortalItem:
    id: UUID
    engagement_id: UUID
    binder_id: UUID
    category_id: UUID | None
    title: str
    group: str  # the request's section card ("Health insurance"): its area
    kind: str  # client_upload | firm_provided
    status: str  # C2, never sent to a client
    client_visible: bool
    client_assignee_user_id: UUID | None
    due_on: date | None  # its own, or the binder's
    requested_at: datetime | None
    client_ignored_at: datetime | None
    ignored_by: UUID | None  # who said it doesn't apply, while the Ignore stands
    guidance: str | None  # firm-written (SPEC-031), or the kind's fixed copy (SPEC-035 AC-5)
    links: tuple[PortalLink, ...]
    uploading: int
    comment_count: int


@dataclass(frozen=True)
class PortalBinderRef:
    id: UUID
    engagement_id: UUID
    work_item_id: UUID
    name: str
    status: str


@dataclass(frozen=True)
class PortalBinder:
    id: UUID
    engagement_id: UUID
    work_item_id: UUID
    name: str
    kind: str
    status: str
    published_at: datetime | None
    marked_done_at: datetime | None
    marked_done_by: UUID | None
    prior_year_source_ref: UUID | None
    categories: tuple[PortalCategory, ...]
    items: tuple[PortalItem, ...]
    delegated_contacts: tuple[UUID, ...]
    firm_acted_since_done: bool  # DEC-24: the client's Undo of Mark as Done is closed


def _ref(binder: RequestList) -> PortalBinderRef:
    return PortalBinderRef(
        binder.id, binder.engagement_id, binder.work_item_id, binder.name, binder.status
    )


async def portal_binder_refs(ctx: AuthContext) -> list[PortalBinderRef]:
    """The binder picker's candidates: every binder the client reads a request of."""
    async with tenant_session(ctx.tenant) as session:
        return [_ref(b) for b in await portal_binders(session, ctx)]


async def portal_binder_ref(ctx: AuthContext, binder_id: UUID) -> PortalBinderRef | None:
    """One binder if a client may read it at all; None for a draft, an unpublished binder or a
    forged id."""
    async with tenant_session(ctx.tenant) as session:
        found = await portal_binder(session, binder_id)
    return _ref(found) if found is not None else None


async def _items(
    session: AsyncSession,
    ctx: AuthContext,
    binder: RequestList,
    rows: Sequence[RequestItem],
    shown: bool,
) -> tuple[PortalItem, ...]:
    ids = [r.id for r in rows]
    links: dict[UUID, list[PortalLink]] = {}
    for f in await live_links(session, ids):
        links.setdefault(f.request_item_id, []).append(
            PortalLink(f.id, f.evidence_version_id, f.created_by_kind, f.created_at)
        )
    uploading = await live_upload_intents(session, ids)
    comments = await list_comment_counts(session, ctx, binder.engagement_id, shared_only=True)
    responses = await client_responses(session, ctx, binder.engagement_id)
    out: list[PortalItem] = []
    for r in rows:
        response = responses.get(r.id)
        ignored_by = (
            response.by_user
            if response is not None
            and response.kind == "not_applicable"
            and r.client_ignored_at is not None
            else None
        )
        swap = for_client(r.guidance_source, r.document_kind, shown)
        out.append(
            PortalItem(
                id=r.id,
                engagement_id=r.engagement_id,
                binder_id=binder.id,
                category_id=r.category_id,
                title=r.title or r.description,
                group=r.audit_area,
                kind=r.kind,
                status=r.status,
                client_visible=r.client_visible,
                client_assignee_user_id=r.client_assignee_user_id,
                due_on=r.due_on or binder.default_due_on,
                requested_at=r.requested_at or r.sent_at,
                client_ignored_at=r.client_ignored_at,
                ignored_by=ignored_by,
                guidance=swap.why if swap is not None else r.why,
                links=tuple(links.get(r.id, ())),
                uploading=uploading.get(r.id, 0),
                comment_count=comments.get(r.id, (0, False))[0],
            )
        )
    return tuple(out)


async def _binder(
    session: AsyncSession, ctx: AuthContext, binder: RequestList, rows: Sequence[RequestItem]
) -> PortalBinder:
    shown = await drafted_guidance_to_clients(ctx.tenant)
    categories = tuple(
        PortalCategory(c.id, c.name, c.position)
        for c in await binder_categories(session, binder.id)
    )
    acted = False
    if binder.status == "complete" and binder.marked_done_at is not None:
        acted = await firm_acted_since(
            session, await binder_items(session, binder.id), binder.marked_done_at
        )
    return PortalBinder(
        id=binder.id,
        engagement_id=binder.engagement_id,
        work_item_id=binder.work_item_id,
        name=binder.name,
        kind=binder.kind,
        status=binder.status,
        published_at=binder.published_at,
        marked_done_at=binder.marked_done_at,
        marked_done_by=binder.marked_done_by,
        prior_year_source_ref=binder.prior_year_source_ref,
        categories=categories,
        items=await _items(session, ctx, binder, rows, shown),
        delegated_contacts=tuple(await binder_delegated_contacts(session, binder.id)),
        firm_acted_since_done=acted,
    )


async def portal_binder_view(ctx: AuthContext, binder_id: UUID) -> PortalBinder | None:
    """One binder as the client reads it, for a caller that authorised `portal_documents.read`
    on it; None when no client may read it."""
    async with tenant_session(ctx.tenant) as session:
        binder = await portal_binder(session, binder_id)
        if binder is None:
            return None
        return await _binder(session, ctx, binder, await portal_items(session, ctx, binder.id))


async def portal_item_binder(ctx: AuthContext, item_id: UUID) -> PortalBinderRef | None:
    """The binder of a request the client reads (to authorise on it), or None (INV-4)."""
    async with tenant_session(ctx.tenant) as session:
        item = await portal_item(session, ctx, item_id)
        if item is None:
            return None
        binder = await portal_binder(session, item.request_list_id)
    return _ref(binder) if binder is not None else None


async def portal_item_view(ctx: AuthContext, item_id: UUID) -> PortalBinder | None:
    """One request in its binder (the binder's `items` hold it alone), for a caller that
    authorised `portal_documents.read` on the binder."""
    async with tenant_session(ctx.tenant) as session:
        item = await portal_item(session, ctx, item_id)
        if item is None:
            return None
        binder = await portal_binder(session, item.request_list_id)
        if binder is None:
            return None
        return await _binder(session, ctx, binder, [item])


async def prior_year_link(
    ctx: AuthContext, binder: PortalBinder, item: PortalItem
) -> tuple[UUID, PortalLink] | None:
    """POR-04's "Last year you sent …": the newest live fulfilment of last year's request of the
    same title, when this binder was rolled forward from one the client reads."""
    if binder.prior_year_source_ref is None:
        return None
    async with tenant_session(ctx.tenant) as session:
        prior = await prior_year_item(session, ctx, binder.prior_year_source_ref, item.title)
        if prior is None:
            return None
        links = await live_links(session, [prior.id])
    if not links:
        return None
    newest = links[-1]
    return prior.id, PortalLink(
        newest.id, newest.evidence_version_id, newest.created_by_kind, newest.created_at
    )


__all__ = [
    "PortalBinder",
    "PortalBinderRef",
    "PortalCategory",
    "PortalItem",
    "PortalLink",
    "portal_binder_ref",
    "portal_binder_refs",
    "portal_binder_view",
    "portal_item_binder",
    "portal_item_view",
    "prior_year_link",
]
