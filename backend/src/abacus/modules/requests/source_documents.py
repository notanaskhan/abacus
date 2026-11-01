"""C5 v1.1's additive request-row facts, the work item's Source Documents aggregate and the AUD-01
PBC counts (A-01-T10; SPEC-330 AC-25 to AC-27; DEC-313; docs/contracts/audits-cockpit.md §3).

- **Owed by** (an open request only: Requested or Returned): an open delegation's contact is a
  `third_party` ("Sam Ortiz, Keystone" delegated by the firm), else the client assignee a
  `client_contact` ("Dana Kowalski"). A request with neither names nobody: nothing records an
  organisation that answers directly yet, so the row says so by leaving `owed_by` out rather than
  guess one.
- **Latest upload** is the newest live fulfilment (a withdrawn version never counts, P-06-T19);
  **Linked (n)** counts the live fulfilments. What requests does not hold itself (the upload's
  path label and uploader, the matcher's confidence) comes from the provider evidence registers
  (`register_upload_facts`); unregistered, there is no latest upload (fail closed).
- **PBC counts** ("11 of 24") read the work item's published PBC binders: received over the
  client-visible requests that are asked (neither Draft nor Not applicable). A work item with no
  published PBC binder has no count at all, so AUD-01 reads "—" before G3 (DEC-39).
- **Source Documents** groups the same requests by category in binder and category order, with
  "n of N" per band that foot to the totals the rail reads.

Firm-only: the assurance routes refuse a client principal, and P-06's binder rows drop these
fields for one (`contract.for_viewer`). Code computes every figure; nothing here calls a model.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Final, Literal
from uuid import UUID

from sqlalchemy import ColumnElement, bindparam, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel import clock
from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.engagements.api import client_contact_names
from abacus.modules.identity.api import AuthContext, names_of, visible, visible_items
from abacus.modules.requests.models import Fulfilment, RequestCategory, RequestItem, RequestList
from abacus.modules.requests.repository import live_fulfilment

OPEN: Final = frozenset({"requested", "returned"})
# A binder whose requests have been asked of the client (a Draft or Unpublished one has not).
ASKED_BINDERS: Final = ("published", "complete", "closed")
# Not asked of the client yet, or not needed: outside "n of N".
UNCOUNTED: Final = ("draft", "not_applicable")
PBC: Final = "pbc"
Sort = Literal["missing_first", "received_first"]
# Missing first (AUD-02, AUD-03): needs review, then requested, then received.
_MISSING_FIRST: Final = {"uploaded": 0, "requested": 1, "returned": 1, "received": 2}
_RECEIVED_FIRST: Final = {"received": 0, "uploaded": 1, "requested": 2, "returned": 2}


@dataclass(frozen=True)
class OwedByView:
    kind: Literal["client_contact", "third_party", "organisation"]
    display: str


@dataclass(frozen=True)
class UploadFacts:
    """What evidence knows of one version: its stored label, when and through which channel it
    arrived, and the matcher's confidence (0-100) that it answers the request, if it matched."""

    path_label: str
    uploaded_on: date
    uploader_kind: Literal["client", "third_party", "firm", "connection"]
    match_confidence: int | None


@dataclass(frozen=True)
class LatestUploadView:
    evidence_version_id: UUID
    path_label: str
    uploaded_on: date
    uploader_kind: str


@dataclass(frozen=True)
class RowFacts:
    owed_by: OwedByView | None
    latest_upload: LatestUploadView | None
    match_confidence: int | None
    linked_count: int | None


# (request item, evidence version) pairs → facts by version id; registered by evidence, which
# owns versions and inbox files and holds the matcher's picks (requests never imports evidence).
UploadFactsProvider = Callable[
    [TenantContext, Sequence[tuple[UUID, UUID]]], Awaitable[Mapping[UUID, UploadFacts]]
]
_upload_facts: UploadFactsProvider | None = None


def register_upload_facts(provider: UploadFactsProvider) -> None:
    global _upload_facts
    if _upload_facts is not None and _upload_facts is not provider:
        raise RuntimeError("the upload facts provider is already registered")
    _upload_facts = provider


async def _live_fulfilments(
    session: AsyncSession, item_ids: Sequence[UUID]
) -> dict[UUID, list[UUID]]:
    """Each item's live fulfilling versions, newest first (for items the caller already read)."""
    if not item_ids:
        return {}
    rows = await session.execute(
        select(Fulfilment.request_item_id, Fulfilment.evidence_version_id)
        .where(Fulfilment.request_item_id.in_(item_ids), live_fulfilment())
        .order_by(Fulfilment.created_at.desc(), Fulfilment.id.desc())
    )
    out: dict[UUID, list[UUID]] = {}
    for item, version in rows.all():
        out.setdefault(item, []).append(version)
    return out


async def _open_delegations(session: AsyncSession, item_ids: Sequence[UUID]) -> dict[UUID, UUID]:
    """The contact of each item's newest open delegation (for items the caller already read)."""
    if not item_ids:
        return {}
    rows = await session.execute(
        text(
            "SELECT request_item_id, contact_id FROM request_delegations "
            "WHERE request_item_id IN :items AND revoked_at IS NULL "
            "ORDER BY granted_at, contact_id"
        ).bindparams(bindparam("items", expanding=True)),
        {"items": list(item_ids)},
    )
    return {item: contact for item, contact in rows.all()}


async def row_facts(
    session: AsyncSession, tenant: TenantContext, items: Sequence[RequestItem]
) -> dict[UUID, RowFacts]:
    """The C5 v1.1 facts of rows the caller already read under `visible_items`."""
    ids = [i.id for i in items]
    fulfilled = await _live_fulfilments(session, ids)
    open_ids = [i.id for i in items if i.status in OPEN]
    delegated = await _open_delegations(session, open_ids)
    contact_names: dict[UUID, str] = {}
    by_engagement: dict[UUID, list[UUID]] = {}
    for item in items:
        if item.id in delegated:
            by_engagement.setdefault(item.engagement_id, []).append(delegated[item.id])
    for engagement_id, contacts in by_engagement.items():
        contact_names |= await client_contact_names(tenant, engagement_id, sorted(set(contacts)))
    assignees = sorted(
        {
            i.client_assignee_user_id
            for i in items
            if i.status in OPEN and i.id not in delegated and i.client_assignee_user_id
        }
    )
    people = await names_of(assignees) if assignees else {}
    latest = {item: versions[0] for item, versions in fulfilled.items()}
    facts: Mapping[UUID, UploadFacts] = {}
    if _upload_facts is not None and latest:
        facts = await _upload_facts(tenant, sorted(latest.items()))
    out: dict[UUID, RowFacts] = {}
    for item in items:
        owed: OwedByView | None = None
        if item.status in OPEN:
            contact = delegated.get(item.id)
            if contact is not None and contact in contact_names:
                owed = OwedByView("third_party", contact_names[contact])
            elif contact is None and item.client_assignee_user_id is not None:
                name = people.get(item.client_assignee_user_id)
                owed = OwedByView("client_contact", name) if name else None
        version = latest.get(item.id)
        found = facts.get(version) if version is not None else None
        upload = (
            None
            if version is None or found is None
            else LatestUploadView(
                version, found.path_label, found.uploaded_on, found.uploader_kind
            )
        )
        linked = len(fulfilled.get(item.id, ()))
        out[item.id] = RowFacts(
            owed_by=owed,
            latest_upload=upload,
            match_confidence=found.match_confidence if found is not None else None,
            linked_count=linked or None,
        )
    return out


# --- AUD-01 PBC counts -------------------------------------------------------------------------


async def _pbc_counts(
    session: AsyncSession,
    work_item_ids: Sequence[UUID],
    reader: ColumnElement[bool] | None,
) -> dict[UUID, tuple[int, int]]:
    binders = select(RequestList.id, RequestList.work_item_id).where(
        RequestList.work_item_id.in_(list(work_item_ids)),
        RequestList.kind == PBC,
        RequestList.status.in_(ASKED_BINDERS),
    )
    if reader is not None:
        binders = binders.where(reader)
    asked = binders.subquery("asked")
    counted = (
        RequestItem.client_visible.is_(True)
        & RequestItem.deleted_at.is_(None)
        & RequestItem.status.not_in(UNCOUNTED)
    )
    rows = await session.execute(
        select(
            asked.c.work_item_id,
            func.count(RequestItem.id).filter(counted & (RequestItem.status == "received")),
            func.count(RequestItem.id).filter(counted),
        )
        .select_from(asked)
        .outerjoin(RequestItem, RequestItem.request_list_id == asked.c.id)
        .group_by(asked.c.work_item_id)
    )
    return {wid: (int(received), int(total)) for wid, received, total in rows.all()}


async def pbc_counts(
    ctx: AuthContext, work_item_ids: Sequence[UUID]
) -> dict[UUID, tuple[int, int]]:
    """(received, total) per work item over its asked PBC binders' client-visible requests; a work
    item without a published PBC binder is absent (AUD-01 reads "—", DEC-39). Counts are
    metadata (ADR-024): filtered with `visible(engagement.read_metadata)`, so a firm admin sees
    them and a walled reader sees none."""
    if not work_item_ids:
        return {}
    async with tenant_session(ctx.tenant) as session:
        return await _pbc_counts(
            session,
            work_item_ids,
            visible(ctx, "engagement.read_metadata", RequestList.engagement_id),
        )


async def pbc_counts_of(
    tenant: TenantContext, work_item_ids: Sequence[UUID]
) -> dict[UUID, tuple[int, int]]:
    """`pbc_counts` for a caller that has already authorised a read of these work items'
    engagements (the cockpit's Source Documents row)."""
    if not work_item_ids:
        return {}
    async with tenant_session(tenant) as session:
        return await _pbc_counts(session, work_item_ids, None)


# --- Source Documents (AUD-02 canvas, AUD-03) --------------------------------------------------


@dataclass(frozen=True)
class SourceDocumentRow:
    request_item_id: UUID
    binder_id: UUID
    title: str
    status: str
    overdue: bool
    requested_at: datetime | None
    due_on: date | None
    owed_by: OwedByView | None
    latest_upload: LatestUploadView | None
    match_confidence: int | None
    linked_count: int | None


# A-03-T15: the band the sample fan-out's requests sit in, after the categories (AUD-03).
_SAMPLE: Final = UUID(int=1)
SAMPLE_BAND: Final = "Sample-driven"


@dataclass(frozen=True)
class SourceDocumentGroup:
    category_id: UUID | None
    label: str
    received: int
    total: int
    rows: list[SourceDocumentRow]


@dataclass(frozen=True)
class SourceDocuments:
    work_item_id: UUID
    received: int
    total: int
    needs_review: int
    requested: int
    groups: list[SourceDocumentGroup]


@dataclass(frozen=True)
class BinderCard:
    """TAX-03's binder card (T-02-T18): the work item's newest PBC binder, as published."""

    id: UUID
    name: str
    status: str
    published_at: datetime | None
    published_by: UUID | None
    marked_done_at: datetime | None
    marked_done_by: UUID | None
    last_upload_at: datetime | None


async def binder_card(ctx: AuthContext, work_item_id: UUID) -> BinderCard | None:
    """The work item's newest PBC binder the reader may read (any status), or None. The caller
    has authorised on the work item's engagement."""
    async with tenant_session(ctx.tenant) as session:
        found = (
            await session.execute(
                select(RequestList)
                .where(
                    RequestList.work_item_id == work_item_id,
                    RequestList.kind == PBC,
                    visible(ctx, "request_item.read", RequestList.engagement_id),
                )
                .order_by(RequestList.part.desc(), RequestList.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if found is None:
            return None
        last = await session.scalar(
            select(func.max(Fulfilment.created_at))
            .join(RequestItem, RequestItem.id == Fulfilment.request_item_id)
            .where(RequestItem.request_list_id == found.id, live_fulfilment())
        )
    return BinderCard(
        found.id,
        found.name,
        found.status,
        found.published_at,
        found.published_by,
        found.marked_done_at,
        found.marked_done_by,
        last,
    )


async def k1_request_for(
    tenant: TenantContext, work_item_id: UUID, issuer_name: str
) -> UUID | None:
    """T-02-T20: the receiving return's one open request for a K-1 from this issuer ("Schedule
    K-1 from Ridgeline Property Partners, LP"), by code; None when none or several match."""
    pattern = f"%{issuer_name.replace('%', '').replace('_', '')}%"
    async with tenant_session(tenant) as session:
        found = (
            (
                await session.execute(
                    select(RequestItem.id)
                    .join(RequestList, RequestList.id == RequestItem.request_list_id)
                    .where(
                        RequestList.work_item_id == work_item_id,
                        RequestItem.status.in_(OPEN),
                        RequestItem.title.ilike("%K-1%"),
                        RequestItem.title.ilike(pattern),
                    )
                    .limit(2)
                )
            )
            .scalars()
            .all()
        )
    return found[0] if len(found) == 1 else None


async def pbc_binders(ctx: AuthContext, work_item_id: UUID) -> list[UUID]:
    """The work item's asked PBC binders the reader may read, in binder order: the engagement
    export's scope (A-01-T18; DEC-379: a binder id outside these is refused at create). The
    caller has authorised on the work item's engagement."""
    async with tenant_session(ctx.tenant) as session:
        found = await session.execute(
            select(RequestList.id)
            .where(
                RequestList.work_item_id == work_item_id,
                RequestList.kind == PBC,
                RequestList.status.in_(ASKED_BINDERS),
                visible(ctx, "request_item.read", RequestList.engagement_id),
            )
            .order_by(RequestList.part, RequestList.created_at, RequestList.id)
        )
        return list(found.scalars().all())


def _counted(status: str) -> bool:
    return status not in UNCOUNTED


async def source_documents(
    ctx: AuthContext,
    work_item_id: UUID,
    *,
    binder_id: UUID | None = None,
    q: str | None = None,
    sort: Sort = "missing_first",
) -> SourceDocuments:
    """The work item's asked PBC requests the reader may see (`visible_items`), by category in
    binder and category order. The caller has authorised `request_item.read` on the work item's
    engagement; the totals count every visible asked request, `q` and `binder` only narrow."""
    async with tenant_session(ctx.tenant) as session:
        binders = (
            (
                await session.execute(
                    select(RequestList)
                    .where(
                        RequestList.work_item_id == work_item_id,
                        RequestList.kind == PBC,
                        RequestList.status.in_(ASKED_BINDERS),
                        visible(ctx, "request_item.read", RequestList.engagement_id),
                    )
                    .order_by(RequestList.part, RequestList.created_at, RequestList.id)
                )
            )
            .scalars()
            .all()
        )
        if binder_id is not None:
            binders = [b for b in binders if b.id == binder_id]
        order = {b.id: n for n, b in enumerate(binders)}
        defaults = {b.id: b.default_due_on for b in binders}
        lists = list(order)
        items: Sequence[RequestItem] = (
            (
                await session.execute(
                    select(RequestItem)
                    .where(
                        RequestItem.request_list_id.in_(lists),
                        RequestItem.deleted_at.is_(None),
                        RequestItem.status != "draft",
                        visible_items(
                            ctx,
                            "request_item.read",
                            RequestItem.engagement_id,
                            RequestItem.client_visible,
                            RequestItem.client_assignee_user_id,
                        ),
                    )
                    .order_by(RequestItem.created_at, RequestItem.id)
                )
            )
            .scalars()
            .all()
        )
        categories: Sequence[RequestCategory] = (
            (
                await session.execute(
                    select(RequestCategory)
                    .where(RequestCategory.request_list_id.in_(lists))
                    .order_by(RequestCategory.position, RequestCategory.id)
                )
            )
            .scalars()
            .all()
        )
        facts = await row_facts(session, ctx.tenant, items)
    today = await clock.today(ctx.tenant)
    needle = (q or "").strip().lower()
    rank = _MISSING_FIRST if sort == "missing_first" else _RECEIVED_FIRST
    bands: dict[UUID | None, list[SourceDocumentRow]] = {}
    totals: dict[UUID | None, list[str]] = {}
    for item in items:
        # A-03-T15: the sample fan-out's requests are their own band, last (AUD-03).
        key = _SAMPLE if item.wave == "sample" else item.category_id
        totals.setdefault(key, []).append(item.status)
        title = item.title or item.description
        if needle and needle not in title.lower():
            continue
        due = item.due_on or defaults.get(item.request_list_id)
        f = facts[item.id]
        bands.setdefault(key, []).append(
            SourceDocumentRow(
                request_item_id=item.id,
                binder_id=item.request_list_id,
                title=title,
                status=item.status,
                overdue=due is not None and due < today and item.status in OPEN,
                requested_at=item.requested_at,
                due_on=item.due_on,
                owed_by=f.owed_by,
                latest_upload=f.latest_upload,
                match_confidence=f.match_confidence,
                linked_count=f.linked_count,
            )
        )
    for rows in bands.values():
        rows.sort(key=lambda r: rank.get(r.status, len(rank)))  # stable: oldest first within
    by_id = {c.id: c for c in categories}
    category_order = sorted(
        by_id, key=lambda c: (order[by_id[c].request_list_id], by_id[c].position)
    )
    keys: list[UUID | None] = [c for c in category_order if c in totals]
    if None in totals:
        keys.append(None)
    if _SAMPLE in totals:
        keys.append(_SAMPLE)
    groups = [
        SourceDocumentGroup(
            category_id=None if key == _SAMPLE else key,
            label=(
                SAMPLE_BAND if key == _SAMPLE else by_id[key].name if key is not None else "Other"
            ),
            received=sum(1 for s in totals[key] if s == "received"),
            total=sum(1 for s in totals[key] if _counted(s)),
            rows=bands.get(key, []),
        )
        for key in keys
        if not needle or key in bands
    ]
    statuses = [i.status for i in items]
    return SourceDocuments(
        work_item_id=work_item_id,
        received=statuses.count("received"),
        total=sum(1 for s in statuses if _counted(s)),
        needs_review=statuses.count("uploaded"),
        requested=sum(1 for s in statuses if s in OPEN),
        groups=groups,
    )
