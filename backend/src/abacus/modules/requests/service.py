"""Request item rules (TASK-008 design §3). Authorise before any write."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import Final
from uuid import UUID, uuid4

from abacus.kernel.db import TenantContext, tenant_session, transaction_context
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Target, UnitOfWork, uow
from abacus.modules.engagements.api import (
    get_ref,
    lock_ref,
    pin_methodology,
    version_detail,
    work_item_index,
)
from abacus.modules.identity.api import (
    Actor,
    AuthContext,
    ItemFacts,
    SystemContext,
    authorise,
    authorise_items,
    drafted_guidance_to_clients,
    engagement_role_of,
    my_engagements,
)
from abacus.modules.requests.availability import available_datasets
from abacus.modules.requests.classification import (
    KIND_INDEX,
    TIER_INDEX,
    Classification,
    classify,
    document_kind,
)
from abacus.modules.requests.events import (
    DueDatesChanged,
    RequestItemClassified,
    RequestItemCreated,
    RequestItemDocumentKindChanged,
    RequestItemStatusChanged,
)
from abacus.modules.requests.guidance import (
    MAX_LENGTH,
    Guidance,
    after_kind_change,
    estimate_minutes,
    for_client,
    for_new_item,
)
from abacus.modules.requests.models import RequestItem
from abacus.modules.requests.repository import (
    client_home_items,
    default_due_on,
    drop_item_rows,
    fulfilling_versions,
    get_binder,
    get_request_item,
    insert_fulfilment,
    insert_request_item,
    item_keys,
    items_fulfilled_by,
    list_comment_counts,
    list_fulfilled_versions,
    list_request_items,
    mark_received,
    newest_fulfilment,
    overdue_counts,
    overdue_items,
    request_list_for,
    revert_to_requested,
    rule_link,
    screening_subject_row,
    search_items,
    set_classification,
    set_client_fields,
    set_default_due_on,
    set_document_kind,
    set_due_dates,
    set_guidance,
    set_status,
    upload_link,
    void_fulfilments,
    void_rule_link,
)
from abacus.modules.requests.workbook import SheetPreview, normalise, preview, read_rows

# F-03-T15: the statuses that take evidence (an upload, a retrieval, a firm file).
TAKES_EVIDENCE: Final = frozenset({"draft", "requested", "uploaded", "returned"})


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
    # SPEC-020: whether client users see it, and the client contributor it's assigned to.
    client_visible: bool = True
    client_assignee_user_id: UUID | None = None
    # SPEC-022: what an A item needs, where its tier came from, and whether the live connection
    # can deliver it now.
    dataset: str | None = None
    tier_source: str | None = None
    available: bool = False
    # SPEC-027 (TASK-051): the item's own due date (None: the request list's default applies).
    due_on: date | None = None
    # SPEC-029 (TASK-055): the document it expects, and whether a rule or the team set it.
    document_kind: str | None = None
    document_kind_source: str | None = None
    # SPEC-031 (TASK-060): what the client reads, and how the firm plans the item.
    why: str | None = None
    good_looks_like: str | None = None
    still_needed: str | None = None
    blocks_fieldwork: bool = False
    effort: str | None = None
    guidance_source: str | None = None
    guidance_approved_by: UUID | None = None  # SPEC-035: who approved drafted guidance
    # SPEC-032 (TASK-062): comments the reader may see on it and its versions; any unread.
    comment_count: int = 0
    unread_comments: bool = False


def _view(
    item: RequestItem,
    evidence_version_id: UUID | None = None,
    available: frozenset[str] = frozenset(),
) -> RequestItemView:
    return RequestItemView(
        item.id,
        item.engagement_id,
        item.description,
        item.audit_area,
        item.status,
        item.created_at,
        evidence_version_id,
        item.retrievability_tier,
        item.client_visible,
        item.client_assignee_user_id,
        item.dataset,
        item.tier_source,
        item.dataset is not None and item.dataset in available,
        item.due_on,
        item.document_kind,
        item.document_kind_source,
        item.why,
        item.good_looks_like,
        item.still_needed,
        item.blocks_fieldwork,
        item.effort,
        item.guidance_source,
        item.guidance_approved_by,
    )


def _guidance(item: RequestItem) -> Guidance:
    return Guidance(
        item.why, item.good_looks_like, item.blocks_fieldwork, item.effort, item.guidance_source
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
        item = await _insert_item(
            tx,
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
    await authorise_items(ctx, "request_item.read", ref.resource())
    client = await engagement_role_of(ctx.tenant, engagement_id, ctx.user_id) in (
        "client_admin",
        "client_contributor",
    )
    async with tenant_session(ctx.tenant) as session:
        rows = await list_request_items(session, ctx, engagement_id)
        counts = await list_comment_counts(session, ctx, engagement_id, shared_only=client)
    datasets = await available_datasets(ctx.tenant, ref.client_entity_id)
    shown = await drafted_guidance_to_clients(ctx.tenant) if client else True
    views: list[RequestItemView] = []
    for item, version_id in rows:
        view = _view(item, version_id, datasets)
        if (c := counts.get(item.id)) is not None:
            view = replace(view, comment_count=c[0], unread_comments=c[1])
        if client:
            view = replace(view, guidance_approved_by=None)
            swap = for_client(item.guidance_source, item.document_kind, shown)
            if swap is not None:  # SPEC-035 AC-5 (ADR-111): not shown to clients
                view = replace(
                    view,
                    why=swap.why,
                    good_looks_like=swap.good_looks_like,
                    guidance_source=swap.source,
                )
        views.append(view)
    return views


@dataclass(frozen=True)
class AppliedMethodology:
    version_id: UUID
    items_created: int


async def insert_classified(
    tx: UnitOfWork,
    ctx: AuthContext,
    engagement_id: UUID,
    request_list_id: UUID,
    description: str,
    audit_area: str,
    firm_tier: str | None,
    template: Guidance | None = None,
) -> UUID:
    """A template item seeded as a request item, inside the caller's unit of work (SPEC-025
    TASK-048: the template's additions in a roll-forward)."""
    item_id = uuid4()
    await _insert_item(
        tx,
        item_id=item_id,
        tenant_id=ctx.tenant_id,
        engagement_id=engagement_id,
        request_list_id=request_list_id,
        description=description,
        audit_area=audit_area,
        created_by=ctx.user_id,
        firm_tier=firm_tier,
        template=template,
    )
    tx.record(
        "request_item.created",
        target=Target("request_item", item_id),
        after=Ref(engagement_id=engagement_id),
    )
    tx.emit(RequestItemCreated(request_item_id=item_id, engagement_id=engagement_id))
    return item_id


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
            await _insert_item(
                tx,
                item_id=item_id,
                tenant_id=ctx.tenant_id,
                engagement_id=engagement_id,
                request_list_id=list_id,
                description=template_item.description,
                audit_area=names[template_item.area_code],
                created_by=ctx.user_id,
                firm_tier=template_item.tier,
                template=Guidance(
                    template_item.why,
                    template_item.good_looks_like,
                    template_item.blocks_fieldwork,
                    template_item.effort,
                    template_item.guidance_source,
                    template_item.guidance_approved_by,
                ),
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
    client_visible: bool = True
    client_assignee_user_id: UUID | None = None
    document_kind: str | None = None  # SPEC-031: the bank statement gap

    @property
    def facts(self) -> ItemFacts:
        """For the client conditions in `authorise` (SPEC-020)."""
        return ItemFacts(self.client_visible, self.client_assignee_user_id)


async def item_ref(tx: UnitOfWork, request_item_id: UUID, *, lock: bool = False) -> RequestItemRef:
    """The item as this transaction sees it (`NotFound` outside the tenant); `lock` holds its row
    for the rest of the transaction."""
    item = await get_request_item(tx.session, request_item_id, lock=lock)
    if item is None:
        raise NotFound("request_item")
    return RequestItemRef(
        item.id,
        item.engagement_id,
        item.status,
        item.client_visible,
        item.client_assignee_user_id,
    )


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
    if item.status not in TAKES_EVIDENCE:
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
            "request_item.uploaded",  # F-03-T15: v2 word for an upload
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
_REVIEWABLE = ("uploaded", "returned")
_AFTER_REVIEW = frozenset({"received", "uploaded", "requested", "returned"})


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


async def reopen_after_undo(
    tx: UnitOfWork, request_item_id: UUID, decided_to: str, back_to: str = "uploaded"
) -> None:
    """Put an item back to the status it had before its review decision, once that decision is
    undone (P-01-T13; DEC-24), inside the Undo's unit of work. The caller has authorised the Undo
    and locked the item (`review_targets`). `decided_to` is where the decision moved it (a reject
    of a firm-only item stays a draft, 0071, so `draft` is accepted then too); `back_to` is
    `uploaded` or `returned`. A decision that moved nothing (a send-back of an item already
    returned) is undone by moving nothing. Audited `request_item.<back_to>`, and
    `request_item.status_changed` is emitted, when the item moves."""
    if decided_to not in _AFTER_REVIEW:
        raise ValueError(f"a review decision never moved an item to {decided_to!r}")
    if back_to not in _REVIEWABLE:
        raise ValueError(f"an undone review decision can't put an item in {back_to!r}")
    item = await item_ref(tx, request_item_id)
    if item.status == back_to:
        return
    allowed = (decided_to, "draft") if decided_to == "requested" else (decided_to,)
    if not await set_status(tx.session, request_item_id, allowed_from=allowed, to=back_to):
        raise ItemNotFulfillable(item.status)
    tx.record(f"request_item.{back_to}", target=Target("request_item", request_item_id))
    tx.emit(
        RequestItemStatusChanged(
            request_item_id=request_item_id,
            engagement_id=item.engagement_id,
            from_status=item.status,
            to_status=back_to,
        )
    )


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
            await _insert_item(
                tx,
                item_id=item_id,
                tenant_id=ctx.tenant_id,
                engagement_id=engagement_id,
                request_list_id=list_id,
                description=row.description,
                audit_area=area_name,
                created_by=ctx.user_id,
                firm_tier=row.tier,
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


# --- Client facts and uploads (SPEC-020; TASK-035) ---------------------------------------------


class NotAClientContributor(DomainConflict):
    """Items are assigned to the engagement's client contributors only (TASK-035 D4)."""

    code = "not_a_client_contributor"


async def _locked_item(tx: UnitOfWork, engagement_id: UUID, item_id: UUID) -> RequestItemRef:
    item = await item_ref(tx, item_id, lock=True)
    if item.engagement_id != engagement_id:
        raise NotFound("request_item")
    return item


async def set_client_visibility(
    ctx: AuthContext, engagement_id: UUID, item_id: UUID, *, client_visible: bool
) -> RequestItemView:
    """Show or hide the item from client users (`request_item.update`; TASK-035 D3)."""
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        item = await _locked_item(tx, engagement_id, item_id)
        await authorise(ctx, "request_item.update", ref.resource())
        await set_client_fields(tx.session, item_id, client_visible=client_visible)
        tx.record(
            "request_item.client_visibility_changed",
            target=Target("request_item", item_id),
            before=Ref(client_visible=int(item.client_visible)),
            after=Ref(client_visible=int(client_visible)),
        )
        return await _item_view(tx, item_id)


async def assign_to_client(
    ctx: AuthContext, engagement_id: UUID, item_id: UUID, *, user_id: UUID | None
) -> RequestItemView:
    """Assign the item to one of the engagement's client contributors, or clear it
    (`request_item.assign`; TASK-035 D4)."""
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        item = await _locked_item(tx, engagement_id, item_id)
        await authorise(ctx, "request_item.assign", ref.resource())
        if user_id is not None:
            role = await engagement_role_of(ctx.tenant, engagement_id, user_id)
            if role != "client_contributor":
                raise NotAClientContributor
        await set_client_fields(tx.session, item_id, client_assignee=user_id)
        tx.record(
            "request_item.client_assigned",
            target=Target("request_item", item_id),
            before=Ref(user_id=item.client_assignee_user_id)
            if item.client_assignee_user_id is not None
            else None,
            after=Ref(user_id=user_id) if user_id is not None else None,
        )
        return await _item_view(tx, item_id)


async def _item_view(tx: UnitOfWork, item_id: UUID) -> RequestItemView:
    item = await get_request_item(tx.session, item_id)
    if item is None:
        raise NotFound("request_item")
    return _view(item, await newest_fulfilment(tx.session, item_id))


async def item_versions(tx: UnitOfWork, item_id: UUID) -> list[UUID]:
    """Every version fulfilling the item, oldest first, for a caller that authorised on it."""
    return list(await fulfilling_versions(tx.session, item_id))


async def fulfil_by_upload(
    tx: UnitOfWork, *, request_item_id: UUID, evidence_version_id: UUID
) -> FulfilmentRef:
    """Link an uploaded version to its item and move the item to `received` (TASK-035 D5). The
    caller authorised `evidence.upload` on this item, with its facts, and holds its lock."""
    tenant = await transaction_context(tx.session)
    item = await item_ref(tx, request_item_id)
    if item.status not in TAKES_EVIDENCE:
        raise ItemNotFulfillable(item.status)
    fulfilment_id = await insert_fulfilment(
        tx.session,
        tenant_id=tenant.tenant_id,
        engagement_id=item.engagement_id,
        request_item_id=request_item_id,
        evidence_version_id=evidence_version_id,
        created_by_kind="human",
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
            "request_item.uploaded",  # F-03-T15: v2 word for an upload
            target=Target("request_item", request_item_id),
            after=Ref(evidence_version_id=evidence_version_id),
        )
    return FulfilmentRef(fulfilment_id, received)


async def read_item(tenant: TenantContext, engagement_id: UUID, item_id: UUID) -> RequestItemRef:
    """The item outside a unit of work, for a caller about to authorise on its facts."""
    async with tenant_session(tenant) as session:
        item = await get_request_item(session, item_id)
    if item is None or item.engagement_id != engagement_id:
        raise NotFound("request_item")
    return RequestItemRef(
        item.id,
        item.engagement_id,
        item.status,
        item.client_visible,
        item.client_assignee_user_id,
        item.document_kind,
    )


@dataclass(frozen=True)
class ItemKind:
    id: UUID
    document_kind: str | None
    description: str = ""  # SPEC-030 (TASK-058): what the upload reviewer is told was asked for


async def upload_item_of(
    tenant: TenantContext, evidence_version_id: UUID, uploader: str
) -> UUID | None:
    """P-06-T19: the request item a person's upload was made to (not a later link)."""
    async with tenant_session(tenant) as session:
        return await upload_link(session, evidence_version_id, uploader)


@dataclass(frozen=True)
class VoidedRuleLink:
    """A rule link a person voided (R-01 Story 2.2), and where its request now stands."""

    fulfilment_id: UUID
    request_item_id: UUID
    evidence_version_id: UUID
    request_status: str
    voided_at: datetime


async def lock_rule_link(
    tx: UnitOfWork, *, engagement_id: UUID, fulfilment_id: UUID
) -> UUID | None:
    """The version a live rule link of the engagement links, with its request item locked first,
    in the caller's unit of work: an accept locks the item before it records its decision, so a
    void that locks it too either waits for the accept and then sees it, or goes first (the
    accept then finds no live link). Evidence checks the version was never accepted next."""
    found = await rule_link(tx.session, fulfilment_id, engagement_id)
    if found is None:
        return None
    item_id, version_id = found
    await get_request_item(tx.session, item_id, lock=True)
    still = await rule_link(tx.session, fulfilment_id, engagement_id)  # read again, under lock
    return version_id if still == found else None


async def void_rule_link_in(
    tx: UnitOfWork, *, engagement_id: UUID, fulfilment_id: UUID, voided_by: UUID
) -> VoidedRuleLink | None:
    """R-01 Story 2.2, inside the caller's unit of work (a person's, already authorised for
    `fulfilment.confirm`): stamp the rule link void, audit `fulfilment.voided`, and return the
    request to `requested` when nothing else fulfils it. None when there is no live rule link."""
    voided = await void_rule_link(tx.session, fulfilment_id, engagement_id, voided_by)
    if voided is None:
        return None
    locked = await get_request_item(tx.session, voided.request_item_id, lock=True)
    if locked is None:  # a fulfilment's item is never deleted (foreign key)
        raise NotFound("request_item")
    tx.record(
        "fulfilment.voided",
        target=Target("fulfilment", fulfilment_id),
        after=Ref(
            request_item_id=voided.request_item_id,
            evidence_version_id=voided.evidence_version_id,
        ),
    )
    before = locked.status
    reverted = await revert_to_requested(tx.session, voided.request_item_id)
    # The item's Activity: a wrong rule link was voided (identifiers only).
    tx.record(
        "request_item.rule_link_voided",
        target=Target("request_item", voided.request_item_id),
        after=Ref(fulfilment_id=fulfilment_id, reverted=int(reverted)),
    )
    if reverted:
        tx.emit(
            RequestItemStatusChanged(
                request_item_id=voided.request_item_id,
                engagement_id=engagement_id,
                from_status="uploaded",
                to_status="requested",
            )
        )
    return VoidedRuleLink(
        fulfilment_id,
        voided.request_item_id,
        voided.evidence_version_id,
        "requested" if reverted else before,
        voided.voided_at,
    )


async def withdraw_upload(
    tx: UnitOfWork, *, evidence_version_id: UUID, withdrawn_by: UUID, item_ids: Sequence[UUID]
) -> list[UUID]:
    """P-06-T19 (ADR-162 §4): inside the withdrawal's unit of work, void the version's
    fulfilments of `item_ids` (the items the withdrawing client may withdraw from) and return to
    `requested` each item it was the only fulfilment of. Returns the items voided."""
    voided = await void_fulfilments(
        tx.session,
        evidence_version_id=evidence_version_id,
        withdrawn_by=withdrawn_by,
        item_ids=item_ids,
    )
    items: list[UUID] = []
    for fulfilment_id, item_id in voided:
        await get_request_item(tx.session, item_id, lock=True)
        tx.record(
            "fulfilment.withdrawn",
            target=Target("fulfilment", fulfilment_id),
            after=Ref(request_item_id=item_id, evidence_version_id=evidence_version_id),
        )
        reverted = await revert_to_requested(tx.session, item_id)
        # The item's Activity: the client withdrew an upload (identifiers only, no file name).
        tx.record(
            "request_item.upload_withdrawn",
            target=Target("request_item", item_id),
            after=Ref(evidence_version_id=evidence_version_id, reverted=int(reverted)),
        )
        items.append(item_id)
    return items


async def items_of_version(tenant: TenantContext, evidence_version_id: UUID) -> list[ItemKind]:
    """The items a version fulfils and the document each expects (SPEC-029; TASK-055), for a
    caller acting as the system on the engagement's own uploads."""
    async with tenant_session(tenant) as session:
        items = await items_fulfilled_by(session, evidence_version_id)
    return [ItemKind(i.id, i.document_kind, i.description) for i in items]


async def latest_version_of(tenant: TenantContext, item_id: UUID) -> UUID | None:
    """The version that last fulfilled the item (TASK-055 D5), for a system caller."""
    async with tenant_session(tenant) as session:
        return await newest_fulfilment(session, item_id)


@dataclass(frozen=True)
class ScreeningSubject:
    """What a request batch's screening is composed against (P-06-T20): the request, the period
    it expects, and its binder's work-item kind (the TRI gate reads it)."""

    id: UUID
    engagement_id: UUID
    title: str
    period_start: date | None
    period_end: date | None
    work_item_kind: str | None


async def screening_subject(tenant: TenantContext, item_id: UUID) -> ScreeningSubject | None:
    """For a system caller composing the item's screening, or a caller that authorised on its
    engagement; None outside the tenant or for a deleted draft."""
    async with tenant_session(tenant) as session:
        row = await screening_subject_row(session, item_id, work_item_index())
    if row is None or row[0].deleted_at is not None:
        return None
    item, kind = row
    return ScreeningSubject(
        item.id,
        item.engagement_id,
        item.title or item.description,
        item.period_start,
        item.period_end,
        kind,
    )


async def read_item_versions(tenant: TenantContext, item_id: UUID) -> list[UUID]:
    """Every version fulfilling the item, oldest first, for a caller that authorised on it."""
    async with tenant_session(tenant) as session:
        return list(await fulfilling_versions(session, item_id))


# --- Classification (SPEC-022; TASK-038) -------------------------------------------------------


async def _insert_item(
    tx: UnitOfWork,
    *,
    item_id: UUID,
    tenant_id: UUID,
    engagement_id: UUID,
    request_list_id: UUID,
    description: str,
    audit_area: str,
    created_by: UUID,
    firm_tier: str | None = None,
    template: Guidance | None = None,
) -> RequestItem:
    """Insert an item classified by `classify` (AC-1), recording how, with its guidance from the
    template or its document kind (SPEC-031 AC-2)."""
    found = classify(description, audit_area, firm_tier=firm_tier)
    kind = document_kind(description, audit_area)  # SPEC-029 (TASK-055)
    item = await insert_request_item(
        tx.session,
        item_id=item_id,
        tenant_id=tenant_id,
        engagement_id=engagement_id,
        request_list_id=request_list_id,
        description=description,
        audit_area=audit_area,
        created_by=created_by,
        retrievability_tier=found.tier,
        dataset=found.dataset,
        tier_source=found.source,
        tier_rule=found.rule_id,
        document_kind=kind,
        document_kind_source="rule" if kind is not None else None,
        guidance=for_new_item(template, kind),
    )
    _record_classified(tx, item_id, engagement_id, found, "request_item.classified")
    return item


def _record_classified(
    tx: UnitOfWork, item_id: UUID, engagement_id: UUID, found: Classification, action: str
) -> None:
    if found.tier is None and action == "request_item.classified":
        return
    tx.record(
        action,
        target=Target("request_item", item_id),
        after=Ref(
            tier=TIER_INDEX.get(found.tier or "", 0),
            rule=hashlib.sha256((found.rule_id or "").encode()).hexdigest(),
        ),
    )
    if found.tier == "A" and found.dataset is not None:
        tx.emit(RequestItemClassified(request_item_id=item_id, engagement_id=engagement_id))


async def reclassify_described(tx: UnitOfWork, item: RequestItem, description: str) -> None:
    """SPEC-022 §12: a changed description is classified again by the rules, unless a person
    overrode the tier or the firm's methodology set it (§4's order; TASK-1232)."""
    if item.tier_source in ("override", "methodology"):
        return
    found = classify(description, item.audit_area)
    if (found.tier, found.dataset, found.source, found.rule_id) == (
        item.retrievability_tier,
        item.dataset,
        item.tier_source,
        item.tier_rule,
    ):
        return
    await set_classification(
        tx.session,
        item.id,
        tier=found.tier,
        dataset=found.dataset,
        source=found.source,
        rule=found.rule_id,
    )
    _record_classified(tx, item.id, item.engagement_id, found, "request_item.classified")


async def set_tier(
    ctx: AuthContext, engagement_id: UUID, item_id: UUID, *, tier: str | None
) -> RequestItemView:
    """AC-2: override the item's tier, or clear the override (the rules then apply again)."""
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await _locked_item(tx, engagement_id, item_id)
        await authorise(ctx, "request_item.update", ref.resource())
        row = await get_request_item(tx.session, item_id)
        if row is None:
            raise NotFound("request_item")
        found = classify(row.description, row.audit_area, override=tier)
        await set_classification(
            tx.session,
            item_id,
            tier=found.tier,
            dataset=found.dataset,
            source=found.source,
            rule=found.rule_id,
        )
        _record_classified(tx, item_id, engagement_id, found, "request_item.tier_overridden")
        return await _item_view(tx, item_id)


async def set_item_document_kind(
    ctx: AuthContext,
    engagement_id: UUID,
    item_id: UUID,
    *,
    kind: str | None,
    clear: bool = False,
) -> RequestItemView:
    """SPEC-029 AC-5 (TASK-055): the team sets the document the item expects (`kind`, or None for
    "no particular document"); `clear` removes the override, and the rules apply again. Evidence
    checks the latest upload again (D5)."""
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await _locked_item(tx, engagement_id, item_id)
        await authorise(ctx, "request_item.update", ref.resource())
        row = await get_request_item(tx.session, item_id)
        if row is None:
            raise NotFound("request_item")
        if clear:
            ruled = document_kind(row.description, row.audit_area)
            new_kind, source = ruled, ("rule" if ruled is not None else None)
        else:
            new_kind, source = kind, "override"
        await set_document_kind(tx.session, item_id, kind=new_kind, source=source)
        followed = after_kind_change(_guidance(row), new_kind)  # SPEC-031: the kind's copy
        if followed is not None:
            await set_guidance(tx.session, item_id, followed)
        tx.record(
            "request_item.document_kind_set",
            target=Target("request_item", item_id),
            after=Ref(
                kind=KIND_INDEX.get(new_kind or "", 0), overridden=int(source == "override")
            ),
        )
        tx.emit(
            RequestItemDocumentKindChanged(request_item_id=item_id, engagement_id=engagement_id)
        )
        return await _item_view(tx, item_id)


# --- Guidance (SPEC-031; TASK-060) --------------------------------------------------------------


@dataclass(frozen=True)
class GuidanceEdit:
    why: str | None
    good_looks_like: str | None
    still_needed: str | None
    blocks_fieldwork: bool
    effort: str | None


def _cleaned(text: str | None) -> str | None:
    stripped = (text or "").strip()
    if len(stripped) > MAX_LENGTH:
        raise DomainInvalid("guidance text is too long")
    return stripped or None


async def set_item_guidance(
    ctx: AuthContext, engagement_id: UUID, item_id: UUID, edit: GuidanceEdit
) -> RequestItemView:
    """AC-3: partner, manager and senior write the item's guidance; it's the firm's from then on
    (kind changes no longer replace it)."""
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await _locked_item(tx, engagement_id, item_id)
        await authorise(ctx, "request_item.update", ref.resource())
        guidance = Guidance(
            _cleaned(edit.why),
            _cleaned(edit.good_looks_like),
            edit.blocks_fieldwork,
            edit.effort,
            "firm",
        )
        await set_guidance(tx.session, item_id, guidance, still_needed=_cleaned(edit.still_needed))
        tx.record(
            "request_item.guidance_set",
            target=Target("request_item", item_id),
            after=Ref(
                blocks_fieldwork=int(edit.blocks_fieldwork),
                effort=EFFORT_INDEX.get(edit.effort or "", 0),
            ),
        )
        return await _item_view(tx, item_id)


EFFORT_INDEX = {"small": 1, "medium": 2, "large": 3}
OPEN_FOR_CLIENT = frozenset({"requested", "returned"})


@dataclass(frozen=True)
class YourPart:
    items_left: int
    blocks_fieldwork: int
    minutes: int


async def your_part(ctx: AuthContext, engagement_id: UUID) -> YourPart:
    """AC-6: the items left for this client user (open or needing revision, assigned to them, or
    unassigned for client admins), how many block fieldwork, and the estimated minutes. Firm
    roles have no part here. Authorised first, so an engagement the caller's grants don't cover
    answers 404 like every other uncovered scope (DEC-43; ED-054), never an unchecked 500."""
    ref = await get_ref(ctx, engagement_id)
    await authorise_items(ctx, "request_item.read", ref.resource())
    role = await engagement_role_of(ctx.tenant, engagement_id, ctx.user_id)
    if role not in ("client_admin", "client_contributor"):
        return YourPart(0, 0, 0)
    # The portal home's own rows (P-08-T13): only a published or done binder's requests, so a
    # draft binder counts nowhere for the client and the two tie (DEC-210; ED-054).
    async with tenant_session(ctx.tenant) as session:
        rows = await client_home_items(session, ctx, engagement_id)
    mine = [
        i
        for i, _, _ in rows
        if i.client_visible
        and i.status in OPEN_FOR_CLIENT
        and (
            i.client_assignee_user_id == ctx.user_id
            or (role == "client_admin" and i.client_assignee_user_id is None)
        )
    ]
    return YourPart(
        len(mine),
        sum(1 for i in mine if i.blocks_fieldwork),
        estimate_minutes([i.effort for i in mine]),
    )


async def apply_drafted_guidance(
    tx: UnitOfWork,
    ctx: AuthContext,
    engagement_id: UUID,
    item_id: UUID,
    *,
    why: str,
    good_looks_like: str,
    effort: str | None,
    blocks_fieldwork: bool | None,
) -> None:
    """SPEC-035 AC-4 (TASK-073): a person approved a drafted guidance text; inside the caller's
    unit of work (agents records the decision there). The source is `drafted`, with who
    approved it; the still-needed note is left as it is."""
    ref = await lock_ref(tx, engagement_id)
    item = await _locked_item(tx, engagement_id, item_id)
    await authorise(ctx, "request_item.update", ref.resource())
    row = await get_request_item(tx.session, item.id)
    if row is None:
        raise NotFound("request_item")
    guidance = Guidance(
        _cleaned(why),
        _cleaned(good_looks_like),
        row.blocks_fieldwork if blocks_fieldwork is None else blocks_fieldwork,
        effort if effort is not None else row.effort,
        "drafted",
    )
    await set_guidance(tx.session, item_id, guidance, approved_by=ctx.user_id)
    tx.record(
        "request_item.drafted_guidance_applied",
        target=Target("request_item", item_id),
        after=Ref(
            blocks_fieldwork=int(guidance.blocks_fieldwork),
            effort=EFFORT_INDEX.get(guidance.effort or "", 0),
        ),
    )


# --- Due dates (SPEC-027 AC-9; TASK-051) ---------------------------------------------------------


async def set_item_due_dates(
    ctx: AuthContext, engagement_id: UUID, item_ids: Sequence[UUID], due_on: date | None
) -> Sequence[RequestItemView]:
    """Set (or clear) several items' due date; a cleared item follows the list's default."""
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "request_item.update", ref.resource())
        changed = await set_due_dates(tx.session, engagement_id, item_ids, due_on)
        if changed != len(set(item_ids)):
            raise NotFound("request_item")
        for item_id in set(item_ids):
            tx.record("request_item.due_date_set", target=Target("request_item", item_id))
        tx.emit(DueDatesChanged(engagement_id=engagement_id))
    return [i for i in await request_items_for(ctx, engagement_id) if i.id in set(item_ids)]


async def list_due_date(ctx: AuthContext, engagement_id: UUID) -> date | None:
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "request_item.read", ref.resource())
    async with tenant_session(ctx.tenant) as session:
        return await default_due_on(session, engagement_id)


async def set_list_due_date(ctx: AuthContext, engagement_id: UUID, due_on: date | None) -> None:
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "request_item.update", ref.resource())
        list_id = await set_default_due_on(tx.session, ctx.tenant_id, engagement_id, due_on)
        tx.record("request_list.default_due_date_set", target=Target("request_list", list_id))
        tx.emit(DueDatesChanged(engagement_id=engagement_id))


@dataclass(frozen=True)
class OverdueItem:
    id: UUID
    description: str
    due_on: date
    client_assignee_user_id: UUID | None


async def overdue_for(
    tenant: TenantContext, engagement_id: UUID, today: date
) -> list[OverdueItem]:
    """For the engagement agent's reminders (SPEC-027 P-4): open or sent-back items past due."""
    async with tenant_session(tenant) as session:
        rows = await overdue_items(session, engagement_id, today)
    return [OverdueItem(i.id, i.description, due, i.client_assignee_user_id) for i, due in rows]


_STAFF_ROLES: Final = frozenset({"engagement_partner", "manager", "senior", "staff"})


async def overdue_mine(ctx: AuthContext, today: date) -> list[tuple[UUID, int]]:
    """TASK-102: per engagement on the caller's team, how many client items are past due."""
    ids = [e for e, role in (await my_engagements(ctx)).items() if role in _STAFF_ROLES]
    async with tenant_session(ctx.tenant) as session:
        counts = await overdue_counts(session, ctx, ids, today)
    return sorted(counts.items(), key=lambda c: -c[1])


SEARCH_LIMIT: Final = 8


async def search_request_items(ctx: AuthContext, q: str) -> list[RequestItem]:
    """SPEC-302 AC-2: request items across the caller's engagements; walls apply."""
    text = q.strip()
    if len(text) < 2:
        return []
    async with tenant_session(ctx.tenant) as session:
        return list(await search_items(session, ctx, text[:100], SEARCH_LIMIT))


# --- R-01-T09: where a portal drop may land ---------------------------------------------------


async def drop_items(tenant: TenantContext, binder_id: UUID) -> Sequence[RequestItemView]:
    """The system sort's candidates in one binder: client-visible, open to evidence (never a
    draft), not delegated. The caller still checks each against the dropper (`member_could`)."""
    async with tenant_session(tenant) as session:
        rows = await drop_item_rows(session, binder_id)
    return [_view(item) for item in rows]


async def drop_target(tx: UnitOfWork, binder_id: UUID, item_id: UUID) -> RequestItemRef | None:
    """Inside the rule link's unit of work (R-01-T09 security review): the request, row-locked,
    while it is still a place the drop may land: its binder published, the request client-visible,
    open, never a draft and not delegated. None otherwise."""
    item = await item_ref(tx, item_id, lock=True)
    binder = await get_binder(tx.session, binder_id)
    if (
        binder is None
        or binder.status != "published"
        or binder.engagement_id != item.engagement_id
    ):
        return None
    still = {row.id for row in await drop_item_rows(tx.session, binder_id)}
    return item if item_id in still else None
