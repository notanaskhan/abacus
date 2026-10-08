"""Request item rules (TASK-008 design §3). Authorise before any write."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from abacus.kernel.db import TenantContext, tenant_session, transaction_context
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import Ref, Target, UnitOfWork, uow
from abacus.modules.engagements.api import get_ref, lock_ref, pin_methodology, version_detail
from abacus.modules.identity.api import Actor, AuthContext, SystemContext, authorise
from abacus.modules.requests.events import RequestItemCreated
from abacus.modules.requests.models import RequestItem
from abacus.modules.requests.repository import (
    get_request_item,
    insert_fulfilment,
    insert_request_item,
    item_keys,
    items_fulfilled_by,
    list_fulfilled_versions,
    list_request_items,
    mark_received,
    newest_fulfilment,
    request_list_for,
    set_status,
)
from abacus.modules.requests.workbook import SheetPreview, normalise, preview, read_rows


@dataclass(frozen=True)
class RequestItemView:
    id: UUID
    engagement_id: UUID
    description: str
    audit_area: str
    status: str
    created_at: datetime
    # The evidence version that last fulfilled the item (the board joins evidence and screening
    # on it; TASK-012 Q1). None until the item has evidence.
    evidence_version_id: UUID | None = None
    # From the methodology template that seeded it (SPEC-008); None for items added by hand.
    retrievability_tier: str | None = None


def _view(item: RequestItem, evidence_version_id: UUID | None = None) -> RequestItemView:
    return RequestItemView(
        item.id,
        item.engagement_id,
        item.description,
        item.audit_area,
        item.status,
        item.created_at,
        evidence_version_id,
        item.retrievability_tier,
    )


@dataclass(frozen=True)
class NewRequestItem:
    description: str
    audit_area: str


async def add_request_item(
    ctx: AuthContext, engagement_id: UUID, new: NewRequestItem
) -> RequestItemView:
    item_id = uuid4()
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "request_item.create", ref.resource())
        list_id, created = await request_list_for(tx.session, ctx.tenant_id, engagement_id)
        if created:
            tx.record(
                "request_list.created",
                target=Target("request_list", list_id),
                after=Ref(engagement_id=engagement_id),
            )
        item = await insert_request_item(
            tx.session,
            item_id=item_id,
            tenant_id=ctx.tenant_id,
            engagement_id=engagement_id,
            request_list_id=list_id,
            description=new.description,
            audit_area=new.audit_area,
            created_by=ctx.user_id,
        )
        tx.record(
            "request_item.created",
            target=Target("request_item", item_id),
            after=Ref(engagement_id=engagement_id),
        )
        tx.emit(RequestItemCreated(request_item_id=item_id, engagement_id=engagement_id))
        view = _view(item)
    return view


async def request_items_for(ctx: AuthContext, engagement_id: UUID) -> Sequence[RequestItemView]:
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "request_item.read", ref.resource())
    async with tenant_session(ctx.tenant) as session:
        rows = await list_request_items(session, ctx, engagement_id)
    return [_view(item, version_id) for item, version_id in rows]


@dataclass(frozen=True)
class AppliedMethodology:
    version_id: UUID
    items_created: int


async def apply_methodology(
    ctx: AuthContext, engagement_id: UUID, version_id: UUID
) -> AppliedMethodology:
    """Pin the engagement to the version and seed one request item per template item, once
    (SPEC-008 AC-4, AC-5; Q4). Existing items are never changed."""
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "engagement.apply_methodology", ref.resource())
        methodology = await pin_methodology(tx, engagement_id, version_id)
        names = {area.code: area.name for area in methodology.areas}
        list_id, created = await request_list_for(tx.session, ctx.tenant_id, engagement_id)
        if created:
            tx.record(
                "request_list.created",
                target=Target("request_list", list_id),
                after=Ref(engagement_id=engagement_id),
            )
        for template_item in methodology.items:
            item_id = uuid4()
            await insert_request_item(
                tx.session,
                item_id=item_id,
                tenant_id=ctx.tenant_id,
                engagement_id=engagement_id,
                request_list_id=list_id,
                description=template_item.description,
                audit_area=names[template_item.area_code],
                created_by=ctx.user_id,
                retrievability_tier=template_item.tier,
            )
            tx.record(
                "request_item.created",
                target=Target("request_item", item_id),
                after=Ref(engagement_id=engagement_id, methodology_version_id=version_id),
            )
            tx.emit(RequestItemCreated(request_item_id=item_id, engagement_id=engagement_id))
        tx.record(
            "methodology.applied",
            target=Target("engagement", engagement_id),
            after=Ref(methodology_version_id=version_id, items=len(methodology.items)),
        )
    return AppliedMethodology(version_id, len(methodology.items))


class ItemNotFulfillable(DomainConflict):
    """Only open or received items take new evidence by rule."""

    code = "item_not_open"


@dataclass(frozen=True)
class RequestItemRef:
    id: UUID
    engagement_id: UUID
    status: str


async def item_ref(tx: UnitOfWork, request_item_id: UUID, *, lock: bool = False) -> RequestItemRef:
    """The item as this transaction sees it (`NotFound` outside the tenant); `lock` holds its row
    for the rest of the transaction."""
    item = await get_request_item(tx.session, request_item_id, lock=lock)
    if item is None:
        raise NotFound("request_item")
    return RequestItemRef(item.id, item.engagement_id, item.status)


@dataclass(frozen=True)
class FulfilmentRef:
    id: UUID | None  # None when this version already fulfilled this item
    received: bool  # the item moved open → received in this call


async def fulfil_by_rule(
    tx: UnitOfWork, ctx: Actor, *, request_item_id: UUID, evidence_version_id: UUID
) -> FulfilmentRef:
    """Link a version to the item it satisfies and move the item `open → received`.

    Authorises `fulfilment.propose` for `ctx` on the item's engagement, inside the caller's unit
    of work (the engagement is share-locked there). The kind follows the actor: the platform's
    links are `rule` (AC-10), a person's are `human`. The evidence must belong to the item's
    engagement (composite key). Only open or received items take new evidence."""
    tenant = await transaction_context(tx.session)
    item = await item_ref(tx, request_item_id, lock=True)
    ref = await lock_ref(tx, item.engagement_id)
    await authorise(ctx, "fulfilment.propose", ref.resource())
    if item.status not in ("open", "received", "needs_revision"):
        raise ItemNotFulfillable(item.status)
    fulfilment_id = await insert_fulfilment(
        tx.session,
        tenant_id=tenant.tenant_id,
        engagement_id=item.engagement_id,
        request_item_id=request_item_id,
        evidence_version_id=evidence_version_id,
        created_by_kind="rule" if isinstance(ctx, SystemContext) else "human",
        created_by_id=tenant.actor_id,
    )
    if fulfilment_id is not None:
        tx.record(
            "fulfilment.created",
            target=Target("fulfilment", fulfilment_id),
            after=Ref(request_item_id=request_item_id, evidence_version_id=evidence_version_id),
        )
    received = await mark_received(tx.session, request_item_id)
    if received:
        tx.record(
            "request_item.received",
            target=Target("request_item", request_item_id),
            after=Ref(evidence_version_id=evidence_version_id),
        )
    return FulfilmentRef(fulfilment_id, received)


@dataclass(frozen=True)
class FulfilledVersion:
    """One evidence version fulfilling one request item (for the review queue, SPEC-004)."""

    request_item_id: UUID
    description: str
    audit_area: str
    item_status: str
    evidence_version_id: UUID
    fulfilled_at: datetime
    fulfilment_id: UUID


async def fulfilled_versions(ctx: AuthContext, engagement_id: UUID) -> list[FulfilledVersion]:
    """The engagement's fulfilled versions the actor may review, `visible()`-filtered. The caller
    has authorised `review.read` on the engagement."""
    async with tenant_session(ctx.tenant) as session:
        rows = await list_fulfilled_versions(session, ctx, engagement_id)
    return [
        FulfilledVersion(
            item.id, item.description, item.audit_area, item.status, version, at, fulfilment_id
        )
        for item, version, at, fulfilment_id in rows
    ]


# A review decision moves its item (SPEC-004 §6, Q2): only from a status that awaits review.
_REVIEWABLE = ("received", "ready_for_review", "needs_revision")
_AFTER_REVIEW = frozenset({"accepted", "received", "open", "needs_revision"})


@dataclass(frozen=True)
class ReviewTarget:
    """An item a version fulfils, locked for the decision: its status, and whether that version
    is still the item's newest evidence."""

    request_item_id: UUID
    status: str
    newest: bool


async def review_targets(tx: UnitOfWork, evidence_version_id: UUID) -> list[ReviewTarget]:
    """Every item the version fulfils, each row locked until the decision commits (so a new
    fulfilment of the item waits for it). For a caller that has authorised the decision."""
    targets: list[ReviewTarget] = []
    for item in await items_fulfilled_by(tx.session, evidence_version_id):
        locked = await item_ref(tx, item.id, lock=True)
        newest = await newest_fulfilment(tx.session, item.id)
        targets.append(ReviewTarget(item.id, locked.status, newest == evidence_version_id))
    return targets


async def move_after_review(tx: UnitOfWork, request_item_id: UUID, to: str) -> None:
    """Apply a review decision's effect on its item, inside the decision's unit of work. The
    caller must have authorised the decision (`evidence.accept` or `evidence.reject`) and locked
    the item (`review_targets`): this moves a status, it checks no rights. Audited
    `request_item.<to>`."""
    if to not in _AFTER_REVIEW:
        raise ValueError(f"a review decision can't move an item to {to!r}")
    item = await item_ref(tx, request_item_id)
    if item.status == to:
        return
    if not await set_status(tx.session, request_item_id, allowed_from=_REVIEWABLE, to=to):
        raise ItemNotFulfillable(item.status)
    tx.record(f"request_item.{to}", target=Target("request_item", request_item_id))


@dataclass(frozen=True)
class RequestItemSummary:
    id: UUID
    description: str
    audit_area: str


async def fulfilled_items(
    tenant: TenantContext, evidence_version_id: UUID
) -> list[RequestItemSummary]:
    async with tenant_session(tenant) as session:
        items = await items_fulfilled_by(session, evidence_version_id)
        return [RequestItemSummary(i.id, i.description, i.audit_area) for i in items]


# --- Request list import (SPEC-018) -------------------------------------------------------------

UNASSIGNED = "Unassigned"


@dataclass(frozen=True)
class ImportCounts:
    created: int
    duplicates: int
    empty: int
    unmatched_areas: int


async def preview_request_list(
    ctx: AuthContext, engagement_id: UUID, data: bytes, header_row: int
) -> list[SheetPreview]:
    """AC-1: nothing stored or audited."""
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "request_item.create", ref.resource())
    return preview(data, header_row)


async def import_request_list(
    ctx: AuthContext,
    engagement_id: UUID,
    data: bytes,
    *,
    sheet: str,
    header_row: int,
    description: int,
    area: int,
    tier: int | None,
) -> ImportCounts:
    """AC-2 to AC-4: one unit of work; duplicates skipped, never changed."""
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "request_item.create", ref.resource())
        rows, empty = read_rows(data, sheet, header_row, description, area, tier)
        areas: dict[str, str] = {}
        if ref.methodology_version_id is not None:
            pinned = await version_detail(ctx.tenant, ref.methodology_version_id)
            for a in pinned.areas:
                areas[normalise(a.name)] = a.name
                areas[normalise(a.code)] = a.name
        seen = {
            (normalise(a), normalise(d))
            for a, d in await item_keys(tx.session, ctx, engagement_id)
        }
        list_id, created_list = await request_list_for(tx.session, ctx.tenant_id, engagement_id)
        if created_list:
            tx.record(
                "request_list.created",
                target=Target("request_list", list_id),
                after=Ref(engagement_id=engagement_id),
            )
        created = duplicates = unmatched = 0
        for row in rows:
            matched = areas.get(normalise(row.area))
            area_name = matched or row.area or UNASSIGNED
            key = (normalise(area_name), normalise(row.description))
            if key in seen:
                duplicates += 1
                continue
            seen.add(key)
            if matched is None and row.area:
                unmatched += 1
            item_id = uuid4()
            await insert_request_item(
                tx.session,
                item_id=item_id,
                tenant_id=ctx.tenant_id,
                engagement_id=engagement_id,
                request_list_id=list_id,
                description=row.description,
                audit_area=area_name,
                created_by=ctx.user_id,
                retrievability_tier=row.tier,
            )
            tx.record(
                "request_item.created",
                target=Target("request_item", item_id),
                after=Ref(engagement_id=engagement_id),
            )
            tx.emit(RequestItemCreated(request_item_id=item_id, engagement_id=engagement_id))
            created += 1
        tx.record(
            "request_list.imported",
            target=Target("request_list", list_id),
            after=Ref(
                source_fingerprint=hashlib.sha256(data).hexdigest(),
                created=created,
                duplicates=duplicates,
                empty=empty,
            ),
        )
    return ImportCounts(created, duplicates, empty, unmatched)
