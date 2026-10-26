"""The binder lifecycle (P-06-T07; C5 v1; SPEC-319 AC-5 to AC-9; DEC-31, DEC-24, ADR-161).

A binder is a `request_list` on a work item (DEC-31): Draft, Published, Unpublished, Complete,
Closed. A named person creates, publishes, unpublishes, duplicates and names its recipients; the
client marks it done; the platform closes it when its work is finished (C1). The agent does none
of these (INV-1: the matrix denies it, and the publish grant is a person's only).

Publish is a client-facing effect: the `binder.published` event is held by an approval grant
(P-04-T10) whose `not_before` is business now + 10 s. Undo within the window voids the grant and
writes the compensating rows, so the relay never delivers the event and no email leaves.

Schema note (no migration in this task): 0071's trigger keeps a request's `draft`/`requested`
in step with its client visibility, so a client-visible request in a Draft binder already reads
`requested`. Publish marks the binder's client-visible, never-sent requests sent (`sent_at`,
`sent_by`); Undo clears them. A client sees nothing of a binder before it is published (INV-4).
"""

from __future__ import annotations

import hashlib
from collections.abc import Awaitable, Callable, Sequence
from contextlib import suppress
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from typing import Final
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel import clock
from abacus.kernel._flags import BINDERS_ENGINE
from abacus.kernel.crypto import open_sealed, seal
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.listing import Position, clamp_limit, decode_cursor, encode_cursor, query_hash
from abacus.kernel.uow import (
    MissingAuditEvent,
    Ref,
    Scope,
    Target,
    TargetEvent,
    UnitOfWork,
    audit_acted_since,
    audit_of_targets,
    audit_total_of_targets,
    event_sha256,
    uow,
)
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.engagements.api import (
    EngagementRef,
    client_contact_names,
    gate_fact,
    get_ref,
    lock_ref,
)
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    ItemFacts,
    Resource,
    allowed_actions,
    authorise,
    authorise_items,
    issue_grant,
    resolve_scope,
    void_grant,
)
from abacus.modules.requests.client_undo import FIRM_ITEM_ACTS, FirmAlreadyActed, NothingToUndo
from abacus.modules.requests.closed_binders import refuse_closed
from abacus.modules.requests.events import (
    BinderClosed,
    BinderMarkDoneUndone,
    BinderMarkedDone,
    BinderPublished,
    BinderUnpublished,
)
from abacus.modules.requests.models import BinderRecipient, RequestItem, RequestList
from abacus.modules.requests.repository import (
    assigned_in_binder,
    binder_categories,
    binder_items,
    get_binder,
    insert_binder,
    insert_categories,
    insert_recipient_rows,
    list_binder_requests,
    list_client_preview,
    next_part,
    open_binders,
    recipient_rows,
    set_binder,
    stamp_sent,
    touch_client_activity,
    upload_counts,
)
from abacus.modules.requests.roll_forward import copy_binder_items
from abacus.modules.requests.source_documents import (
    LatestUploadView,
    OwedByView,
    RowFacts,
    row_facts,
)

# DEC-24: the Undo window of a publish, and how long its grant stays consumable after it.
UNDO_WINDOW: Final = timedelta(seconds=10)
GRANT_LIFETIME: Final = timedelta(days=7)
# INV-4: a client reads a binder only once it is published (and after the client marks it done).
CLIENT_VISIBLE: Final = frozenset({"published", "complete"})
# Requests the client has finished: uploaded, received, or not applicable.
DONE: Final = frozenset({"uploaded", "received", "not_applicable"})
OPEN_REQUEST: Final = frozenset({"requested", "returned"})
# `binder.created`'s reference carries the source as a code (references hold no text).
CREATED_FROM: Final = {"blank": 0, "template": 1, "prior_year_binder": 2, "engine_import": 3}
MAX_PART: Final = 20
_BINDER_ACTIONS: Final = (
    "binder.read",
    "binder.create",
    "binder.update",
    "binder.publish",
    "binder.mark_done",
    "request_item.read",
    "activity.read",
    # P-06-T16: BND-02's "Send reminder…" (follow-ups v2; DEC-74).
    "follow_up.draft",
    "follow_up.send",
)
# Actions a client principal takes on a binder: denied on one it can't see answers 404 (INV-4).
_CLIENT_READS: Final = frozenset({"binder.read", "binder.mark_done", "request_item.read"})


class BinderGateUnmet(DomainConflict):
    """A binder publishes once its engagement meets G3 (the letter), except an intake binder
    (DEC-39)."""

    code = "binder_gate_unmet"


class BinderNotDraft(DomainConflict):
    """Only a Draft or Unpublished binder publishes."""

    code = "binder_not_draft"


class BinderNotPublished(DomainConflict):
    """Unpublish, mark-done and follow-ups act on a Published binder only."""

    code = "binder_not_published"


class DueDateRequired(DomainInvalid):
    """Every request a publish sends needs a due date, its own or the binder's default; the
    facts name the requests without one."""

    code = "due_date_required"


class ReasonRequired(DomainInvalid):
    """Unpublishing a binder needs a reason."""

    code = "reason_required"


class UndoWindowClosed(DomainConflict):
    """Undo is possible for 10 seconds after a publish, and only once."""

    code = "undo_window_closed"


class EffectStarted(DomainConflict):
    """The publish's delivery has started (its grant was consumed): it can no longer be undone."""

    code = "effect_started"


# --- Views (the contract's models are built from these, field for field) ------------------------


@dataclass(frozen=True)
class RecipientView:
    contact_id: UUID
    name: str


@dataclass(frozen=True)
class CategoryView:
    id: UUID
    name: str
    position: int
    done_count: int
    total_count: int


@dataclass(frozen=True)
class BinderView:
    id: UUID
    engagement_id: UUID
    work_item_id: UUID | None
    name: str
    kind: str
    part: int
    status: str
    created_from: str
    prior_year_source_ref: UUID | None
    template_ref: str | None
    default_due_on: date | None
    recipients: list[RecipientView]
    categories: list[CategoryView]
    done_count: int
    total_count: int
    published_at: datetime | None
    published_by: UUID | None
    unpublished_at: datetime | None
    unpublished_by: UUID | None
    unpublish_reason: str | None
    marked_done_at: datetime | None
    marked_done_by: UUID | None
    marked_done_open_count: int | None
    closed_at: datetime | None
    closed_reason: str | None
    follow_up_override: dict[str, object] | None
    undo_until: datetime | None
    allowed_actions: list[str]


@dataclass(frozen=True)
class RequestRowView:
    id: UUID
    category_id: UUID | None
    title: str
    status: str
    overdue: bool
    client_visible: bool
    kind: str
    due_on: date | None
    requested_at: datetime | None
    client_ignored_at: datetime | None
    source_tag: str | None
    incorporation_state: str
    upload_count: int
    # C5 v1.1 (A-01-T10, DEC-313): firm-only; `contract.for_viewer` drops them for a client.
    owed_by: OwedByView | None = None
    latest_upload: LatestUploadView | None = None
    match_confidence: int | None = None
    linked_count: int | None = None


@dataclass(frozen=True)
class RequestPage:
    items: list[RequestRowView]
    next_cursor: str | None
    total: int
    total_capped: bool
    counts: dict[str, int]


@dataclass(frozen=True)
class PreviewItemView:
    id: UUID
    category_name: str | None
    title: str
    description: str
    status: str
    client_ignored: bool
    due_on: date | None


@dataclass(frozen=True)
class PreviewView:
    binder_id: UUID
    name: str
    status: str
    items: list[PreviewItemView]


@dataclass(frozen=True)
class ActivityView:
    id: UUID
    event_type: str
    at: datetime
    actor_kind: str
    actor_user_id: UUID | None
    via_agent: bool
    target_type: str
    target_id: UUID


@dataclass(frozen=True)
class ActivityPage:
    items: list[ActivityView]
    next_cursor: str | None
    total: int
    total_capped: bool


@dataclass(frozen=True)
class MarkDoneUndoneView:
    binder_id: UUID
    mark_done: str  # tonal (requests open) or ready
    undone_at: datetime


@dataclass(frozen=True)
class MarkedDoneView:
    binder_id: UUID
    status: str
    marked_done_at: datetime
    open_count: int


# --- Loading and authorising --------------------------------------------------------------------


async def engine_on(ctx: AuthContext) -> None:
    """`binders.engine` off: every C5 route answers 404."""
    if not await flag_enabled(ctx.tenant, BINDERS_ENGINE):
        raise NotFound("binders.engine")


def _human(ctx: AuthContext, action: str) -> None:
    """INV-1: a person's own decision, never an agent, the platform or a support session."""
    if ctx.tenant.actor_kind != "human" or ctx.is_support:
        raise Forbidden(action, "role")


async def _facts(ctx: AuthContext, binder: RequestList, session: AsyncSession) -> ItemFacts:
    """The binder's client facts, for `client_visible_only` and `assigned_only`: visible once
    published; a contributor's when a client-visible request of it is assigned to them."""
    visible = binder.status in CLIENT_VISIBLE
    assigned = visible and await assigned_in_binder(session, binder.id, ctx.user_id)
    return ItemFacts(visible, ctx.user_id if assigned else None)


def _resource(ref: EngagementRef, binder: RequestList, facts: ItemFacts | None) -> Resource:
    return replace(ref.resource(), item=facts, work_item_id=binder.work_item_id)


async def _authorise(
    ctx: AuthContext, action: str, resource: Resource, *, reason: str | None = None
) -> None:
    try:
        await authorise(ctx, action, resource, reason=reason)
    except Forbidden:
        if action in _CLIENT_READS and resource.item is not None:
            # INV-4: to a client, a binder not published or not in their scope doesn't exist.
            # The denial came from the client conditions when the same person would be allowed
            # on a published binder assigned to them.
            probe = replace(resource, item=ItemFacts(True, ctx.user_id))
            if action in await allowed_actions(ctx, probe, [action]):
                raise NotFound("binder") from None
        raise


async def _readable(
    ctx: AuthContext, binder_id: UUID, action: str
) -> tuple[RequestList, EngagementRef, Resource]:
    async with tenant_session(ctx.tenant) as session:
        binder = await get_binder(session, binder_id)
        if binder is None:
            raise NotFound("binder")
        facts = await _facts(ctx, binder, session)
    ref = await get_ref(ctx, binder.engagement_id)
    resource = _resource(ref, binder, facts)
    await _authorise(ctx, action, resource)
    return binder, ref, resource


async def _locked(
    tx: UnitOfWork, ctx: AuthContext, binder_id: UUID, action: str, *, reason: str | None = None
) -> tuple[RequestList, EngagementRef, Resource]:
    """The binder, row-locked for one lifecycle move, and authorised against the same rows."""
    binder = await get_binder(tx.session, binder_id, lock=True)
    if binder is None:
        raise NotFound("binder")
    ref = await lock_ref(tx, binder.engagement_id)
    resource = _resource(ref, binder, await _facts(ctx, binder, tx.session))
    await _authorise(ctx, action, resource, reason=reason)
    return binder, ref, resource


async def check_action(ctx: AuthContext, binder_id: UUID, action: str) -> None:
    """Authorise `action` on the binder (read-only): a replayed publish is still checked."""
    await _readable(ctx, binder_id, action)


def _scope(binder: RequestList) -> Scope:
    return Scope(engagement_id=binder.engagement_id, work_item_id=binder.work_item_id)


def _reason_context(binder_id: UUID) -> str:
    """What a sealed unpublish reason is bound to (its binder), so it opens without a stored
    fingerprint and never as another binder's."""
    return hashlib.sha256(f"binder.unpublish_reason:{binder_id}".encode()).hexdigest()


async def unpublish_reason(tenant_id: UUID, binder: RequestList) -> str | None:
    """An Unpublished binder's reason, opened for a caller that may read the binder."""
    if binder.status != "unpublished" or binder.unpublish_reason_sealed is None:
        return None
    sealed = await open_sealed(
        tenant_id, binder.unpublish_reason_sealed, _reason_context(binder.id)
    )
    return sealed.decode()


def current_recipients(rows: Sequence[BinderRecipient]) -> list[UUID]:
    """Contacts whose additions outnumber their removals (insert-only history), in the order
    they were first added."""
    balance: dict[UUID, int] = {}
    for row in rows:
        balance[row.contact_id] = balance.get(row.contact_id, 0) + (
            1 if row.removed_at is None else -1
        )
    return [contact for contact, n in balance.items() if n > 0]


async def _last_ref(
    session: AsyncSession, binder_id: UUID, action: str
) -> dict[str, str | int] | None:
    """The `after` reference of the binder's newest `action` audit event."""
    found = await audit_of_targets(session, [("binder", binder_id)], None, 1, action=action)
    return found[0].after_ref if found else None


async def _view(ctx: AuthContext, binder_id: UUID) -> BinderView:
    """The BND-02 record projection, for a caller that authorised `binder.read` on it."""
    async with tenant_session(ctx.tenant) as session:
        binder = await get_binder(session, binder_id)
        if binder is None:
            raise NotFound("binder")
        items = await binder_items(session, binder.id)
        categories = await binder_categories(session, binder.id)
        recipients = current_recipients(await recipient_rows(session, binder.id))
        facts = await _facts(ctx, binder, session)
        done_ref = (
            await _last_ref(session, binder.id, "binder.marked_done")
            if binder.status == "complete"
            else None
        )
    ref = await get_ref(ctx, binder.engagement_id)
    resource = _resource(ref, binder, facts)
    names = await client_contact_names(ctx.tenant, binder.engagement_id, recipients)
    now = await clock.now(ctx.tenant)
    reason = await unpublish_reason(ctx.tenant_id, binder)
    undo_until = None
    if binder.status == "published" and binder.published_at is not None:
        ends = binder.published_at + UNDO_WINDOW
        undo_until = ends if now < ends else None
    allowed = set(await allowed_actions(ctx, resource, _BINDER_ACTIONS))
    if binder.status == "closed":
        allowed -= {"binder.publish", "binder.update"}
    if binder.status != "published":  # only a Published binder's requests are chased
        allowed -= {"follow_up.draft", "follow_up.send"}
    if binder.status != "published":
        allowed.discard("binder.mark_done")
    by_category = {c.id: [i for i in items if i.category_id == c.id] for c in categories}
    open_count = done_ref.get("open") if done_ref else None
    return BinderView(
        id=binder.id,
        engagement_id=binder.engagement_id,
        work_item_id=binder.work_item_id,
        name=binder.name,
        kind=binder.kind,
        part=binder.part,
        status=binder.status,
        created_from=binder.created_from,
        prior_year_source_ref=binder.prior_year_source_ref,
        template_ref=binder.template_ref,
        default_due_on=binder.default_due_on,
        recipients=[RecipientView(c, names[c]) for c in recipients if c in names],
        categories=[
            CategoryView(
                c.id,
                c.name,
                c.position,
                sum(1 for i in by_category[c.id] if i.status in DONE),
                len(by_category[c.id]),
            )
            for c in categories
        ],
        done_count=sum(1 for i in items if i.status in DONE),
        total_count=len(items),
        published_at=binder.published_at,
        published_by=binder.published_by,
        unpublished_at=binder.unpublished_at if binder.status == "unpublished" else None,
        unpublished_by=binder.unpublished_by if binder.status == "unpublished" else None,
        unpublish_reason=reason,
        marked_done_at=binder.marked_done_at,
        marked_done_by=binder.marked_done_by,
        marked_done_open_count=open_count if isinstance(open_count, int) else None,
        closed_at=binder.closed_at,
        closed_reason=binder.closed_reason,
        follow_up_override=binder.follow_up_override,
        undo_until=undo_until,
        allowed_actions=sorted(allowed),
    )


# --- Reads --------------------------------------------------------------------------------------


async def read_binder(ctx: AuthContext, binder_id: UUID) -> BinderView:
    await _readable(ctx, binder_id, "binder.read")
    return await _view(ctx, binder_id)


async def binder_requests(
    ctx: AuthContext, binder_id: UUID, category: UUID | None, cursor: str | None, limit: int = 200
) -> RequestPage:
    """BND-02 rows (oldest first; the screen groups them by `category_id`), through
    `visible_items`: a client sees only client-visible rows of a published binder (INV-4)."""
    binder, ref, resource = await _readable(ctx, binder_id, "binder.read")
    await authorise_items(ctx, "request_item.read", replace(resource, item=None))
    page_size = clamp_limit(limit)
    where = f"binder_requests:{binder.id}"
    query = query_hash(category=category)
    after = (
        decode_cursor(cursor, tenant_id=ctx.tenant_id, resource=where, query=query)
        if cursor
        else None
    )
    async with tenant_session(ctx.tenant) as session:
        rows, counts, total = await list_binder_requests(
            session, ctx, binder.id, category, after, page_size
        )
        uploads = await upload_counts(session, [r.id for r in rows])
        page = list(rows[:page_size])
        facts = await row_facts(session, ctx.tenant, page) if not ctx.client else {}
    following = None
    if len(rows) > page_size and page:
        last = page[-1]
        following = encode_cursor(
            Position(key=last.created_at.isoformat(), id=str(last.id)),
            tenant_id=ctx.tenant_id,
            resource=where,
            query=query,
        )
    today = await clock.today(ctx.tenant)
    del ref
    return RequestPage(
        [
            _row(i, binder.default_due_on, today, uploads.get(i.id, 0), facts.get(i.id))
            for i in page
        ],
        following,
        total[0],
        total[1],
        counts,
    )


def _row(
    item: RequestItem,
    default_due: date | None,
    today: date,
    uploads: int,
    facts: RowFacts | None = None,
) -> RequestRowView:
    due = item.due_on or default_due
    return RequestRowView(
        id=item.id,
        category_id=item.category_id,
        title=item.title or item.description,
        status=item.status,
        overdue=due is not None and due < today and item.status in OPEN_REQUEST,
        client_visible=item.client_visible,
        kind=item.kind,
        due_on=item.due_on,
        requested_at=item.requested_at,
        client_ignored_at=item.client_ignored_at,
        source_tag=item.source_tag,
        incorporation_state=item.incorporation_state,
        upload_count=uploads,
        owed_by=facts.owed_by if facts else None,
        latest_upload=facts.latest_upload if facts else None,
        match_confidence=facts.match_confidence if facts else None,
        linked_count=facts.linked_count if facts else None,
    )


async def client_preview(ctx: AuthContext, binder_id: UUID) -> PreviewView:
    """POR-03 as a recipient will see it: client-visible requests only, the client's words,
    never internal fields (BND-02 "Preview as client")."""
    binder, _ref, _resource = await _readable(ctx, binder_id, "binder.read")
    async with tenant_session(ctx.tenant) as session:
        items = await list_client_preview(session, ctx, binder.id)
        names = {c.id: c.name for c in await binder_categories(session, binder.id)}
    return PreviewView(
        binder.id,
        binder.name,
        binder.status,
        [
            PreviewItemView(
                id=i.id,
                category_name=names.get(i.category_id) if i.category_id else None,
                title=i.title or i.description,
                description=i.description,
                status=i.status,
                client_ignored=i.client_ignored_at is not None,
                due_on=i.due_on or binder.default_due_on,
            )
            for i in items
        ],
    )


async def binder_activity(ctx: AuthContext, binder_id: UUID, cursor: str | None) -> ActivityPage:
    """The binder's and its requests' audit events, newest first, identifiers only (§4.7)."""
    async with tenant_session(ctx.tenant) as session:
        binder = await get_binder(session, binder_id)
        if binder is None:
            raise NotFound("binder")
    ref = await get_ref(ctx, binder.engagement_id)
    await authorise(ctx, "activity.read", _resource(ref, binder, None))
    where = f"binder_activity:{binder.id}"
    query = query_hash(binder=binder.id)
    before = None
    if cursor:
        position = decode_cursor(cursor, tenant_id=ctx.tenant_id, resource=where, query=query)
        if not isinstance(position.key, int):
            raise NotFound("cursor")
        before = position.key
    size = clamp_limit(None)
    async with tenant_session(ctx.tenant) as session:
        items = await binder_items(session, binder.id)
        targets = [("binder", binder.id), *(("request_item", i.id) for i in items)]
        events = await audit_of_targets(session, targets, before, size + 1)
        total = await audit_total_of_targets(session, targets)
    page = events[:size]
    following = (
        encode_cursor(
            Position(key=page[-1].seq, id=str(page[-1].id)),
            tenant_id=ctx.tenant_id,
            resource=where,
            query=query,
        )
        if len(events) > size and page
        else None
    )
    return ActivityPage([_activity(e) for e in page], following, total[0], total[1])


def activity_view(event: TargetEvent) -> ActivityView:
    """One audit event as an activity row (binders and, P-06-T10, a request)."""
    return _activity(event)


def _activity(event: TargetEvent) -> ActivityView:
    kind = event.actor_kind if event.actor_kind in ("human", "agent") else "system"
    person: UUID | None = event.on_behalf_of_user_id
    if kind == "human":
        try:
            person = UUID(event.actor_id)
        except ValueError:
            person = None
    return ActivityView(
        id=event.id,
        event_type=event.action,
        at=event.at,
        actor_kind=kind,
        actor_user_id=person,
        via_agent=kind == "agent" and person is not None,
        target_type=event.target_type,
        target_id=UUID(event.target_id),
    )


# --- Create and duplicate -----------------------------------------------------------------------


async def create_binder(
    ctx: AuthContext,
    *,
    work_item_id: UUID,
    kind: str,
    name: str | None,
    from_binder_id: UUID | None,
    template_ref: str | None,
) -> BinderView:
    """A Draft binder on the work item (DEC-31: many per work item, each kind numbered by part):
    blank, from a firm template (its reference kept; K-01 fills templates), or from last year's
    binder (its sections and requests, by `roll_forward.py`'s rules)."""
    _human(ctx, "binder.create")
    if from_binder_id is not None and template_ref is not None:
        raise DomainInvalid("a binder comes from a template or a prior binder, not both")
    scope = await resolve_scope(ctx.tenant, "work_item", work_item_id)
    if scope is None or scope.engagement_id is None:
        raise NotFound("work_item")
    source: tuple[RequestList, EngagementRef] | None = None
    if from_binder_id is not None:
        found, source_ref, _ = await _readable(ctx, from_binder_id, "binder.read")
        source = (found, source_ref)
    created_from = (
        "prior_year_binder" if source else "template" if template_ref is not None else "blank"
    )
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, scope.engagement_id)
        await authorise(ctx, "binder.create", replace(ref.resource(), work_item_id=work_item_id))
        if source is not None and source[1].client_id != ref.client_id:
            raise DomainInvalid("a prior-year binder is the same client's")
        binder = await _insert(
            tx,
            ctx,
            ref,
            work_item_id,
            kind,
            name,
            created_from=created_from,
            template_ref=template_ref,
            prior=source[0].id if source else None,
        )
        copied = 0
        if source is not None:
            old = await binder_categories(tx.session, source[0].id)
            made = await insert_categories(
                tx.session, ctx.tenant_id, binder.id, [c.name for c in old]
            )
            copied = await copy_binder_items(
                tx,
                ctx,
                source_binder_id=source[0].id,
                binder_id=binder.id,
                engagement_id=binder.engagement_id,
                categories={c.id: made[c.name] for c in old},
            )
        refs: dict[str, UUID | int] = {
            "work_item_id": work_item_id,
            "part": binder.part,
            "created_from": CREATED_FROM[created_from],
            "items": copied,
        }
        if source is not None:
            refs["source_binder_id"] = source[0].id
        tx.record(
            "binder.created",
            target=Target("binder", binder.id),
            after=Ref(**refs),
            scope=_scope(binder),
        )
    return await _view(ctx, binder.id)


async def _insert(
    tx: UnitOfWork,
    ctx: AuthContext,
    ref: EngagementRef,
    work_item_id: UUID,
    kind: str,
    name: str | None,
    *,
    created_from: str,
    template_ref: str | None,
    prior: UUID | None,
) -> RequestList:
    part = await next_part(tx.session, work_item_id, kind)
    if part > MAX_PART:
        raise DomainInvalid("a work item holds at most 20 parts of a binder kind")
    values: dict[str, object] = {
        "id": uuid4(),
        "tenant_id": ctx.tenant_id,
        "engagement_id": ref.id,
        "work_item_id": work_item_id,
        "kind": kind,
        "part": part,
        "status": "draft",
        "created_from": created_from,
        "template_ref": template_ref,
        "prior_year_source_ref": prior,
    }
    if name is not None:
        values["name"] = name
    return await insert_binder(tx.session, **values)


def _part_name(name: str, part: int) -> str:
    """ "2025 Binder" -> "2025 Binder pt 2" (a trailing " pt n" is replaced, not stacked)."""
    base = name
    head, sep, tail = name.rpartition(" pt ")
    if sep and tail.isdigit():
        base = head
    suffix = f" pt {part}"
    return base[: 200 - len(suffix)] + suffix


async def duplicate_binder(ctx: AuthContext, binder_id: UUID) -> BinderView:
    """ "Duplicate as pt n": an empty Draft with the next part, the same recipients and the same
    sections, no requests (OQ-7)."""
    _human(ctx, "binder.create")
    async with uow(ctx.tenant) as tx:
        source, ref, resource = await _locked(tx, ctx, binder_id, "binder.create")
        del resource
        part = await next_part(tx.session, source.work_item_id, source.kind)
        binder = await _insert(
            tx,
            ctx,
            ref,
            source.work_item_id,
            source.kind,
            _part_name(source.name, part),
            created_from="blank",
            template_ref=None,
            prior=None,
        )
        old = await binder_categories(tx.session, source.id)
        await insert_categories(tx.session, ctx.tenant_id, binder.id, [c.name for c in old])
        recipients = current_recipients(await recipient_rows(tx.session, source.id))
        await insert_recipient_rows(
            tx.session,
            [
                {
                    "tenant_id": ctx.tenant_id,
                    "binder_id": binder.id,
                    "contact_id": contact,
                    "added_by": ctx.user_id,
                    "removed_at": None,
                }
                for contact in recipients
            ],
        )
        tx.record(
            "binder.duplicated",
            target=Target("binder", binder.id),
            after=Ref(source_binder_id=source.id, part=binder.part),
            scope=_scope(binder),
        )
    return await _view(ctx, binder.id)


# --- Publish, Undo, unpublish -------------------------------------------------------------------


async def publish_binder(ctx: AuthContext, binder_id: UUID) -> BinderView:
    """Draft or Unpublished to Published (AC-5, AC-6): G3 first except an intake binder (409
    `binder_gate_unmet`), a due date on every request sent (422 `due_date_required`), then the
    binder's client-visible, never-sent requests are sent and the recipients' email waits on a
    grant until the 10-s Undo window ends."""
    _human(ctx, "binder.publish")
    async with uow(ctx.tenant) as tx:
        binder, _ref, resource = await _locked(tx, ctx, binder_id, "binder.publish")
        if binder.status not in ("draft", "unpublished"):
            raise BinderNotDraft(facts={"status": binder.status})
        if binder.kind != "intake":
            gate = await gate_fact(ctx.tenant, binder.engagement_id, "G3")
            if not gate.met:
                raise BinderGateUnmet(facts={"gate": "G3"})
        items = await binder_items(tx.session, binder.id)
        to_send = [
            i
            for i in items
            if i.client_visible and i.sent_at is None and i.status in ("draft", "requested")
        ]
        undated = [i.id for i in to_send if i.due_on is None and binder.default_due_on is None]
        if undated:
            facts: dict[str, object] = {"count": len(undated)}
            facts.update({f"request_item_{n}": str(i) for n, i in enumerate(undated[:20])})
            raise DueDateRequired(facts=facts)
        now = await clock.now(ctx.tenant)
        undo_until = now + UNDO_WINDOW
        await set_binder(
            tx.session,
            binder.id,
            allowed_from=("draft", "unpublished"),
            status="published",
            published_at=now,
            published_by=ctx.user_id,
        )
        sent = [i.id for i in to_send]
        await stamp_sent(tx.session, sent, at=now, by=ctx.user_id)
        event = BinderPublished(
            binder_id=binder.id,
            engagement_id=binder.engagement_id,
            work_item_id=binder.work_item_id,
            published_by=ctx.user_id,
            recipient_contact_ids=current_recipients(await recipient_rows(tx.session, binder.id)),
            request_item_ids=sent,
        )
        grant = await issue_grant(
            tx,
            ctx,
            action="binder.publish",
            resource=resource,
            subject=Target("binder", binder.id),
            payload_sha256=event_sha256(event),
            not_before=undo_until,
            expires_at=undo_until + GRANT_LIFETIME,
        )
        tx.emit(event, not_before=undo_until, grant_id=grant)
        tx.record(
            "binder.published",
            target=Target("binder", binder.id),
            after=Ref(
                grant=grant,
                items=len(sent),
                from_unpublished=int(binder.status == "unpublished"),
            ),
            scope=_scope(binder),
        )
        for item_id in sent:
            tx.record(
                "request_item.sent",
                target=Target("request_item", item_id),
                after=Ref(binder_id=binder.id, grant=grant),
                scope=_scope(binder),
            )
    return await _view(ctx, binder_id)


async def undo_publish(ctx: AuthContext, binder_id: UUID) -> BinderView:
    """Within 10 s of a publish: void its grant (so no email leaves) and put the binder and its
    requests back as they were. Later, 409 `undo_window_closed`; once the delivery has consumed
    the grant, 409 `effect_started`."""
    _human(ctx, "binder.publish")
    async with uow(ctx.tenant) as tx:
        binder, _ref, _resource = await _locked(tx, ctx, binder_id, "binder.publish")
        now = await clock.now(ctx.tenant)
        published_at = binder.published_at
        if binder.status != "published" or published_at is None:
            raise UndoWindowClosed
        # ADR-161 clause 6: only the person who published may undo it (ED-022).
        if binder.published_by != ctx.user_id or now >= published_at + UNDO_WINDOW:
            raise UndoWindowClosed
        published = await _last_ref(tx.session, binder.id, "binder.published")
        grant = _uuid_of(published.get("grant")) if published else None
        if grant is None or not await void_grant(tx, grant):
            raise EffectStarted
        back = "unpublished" if published and published.get("from_unpublished") == 1 else "draft"
        items = await binder_items(tx.session, binder.id)
        unsent = [
            i.id for i in items if i.sent_at == published_at and i.sent_by == binder.published_by
        ]
        await set_binder(
            tx.session,
            binder.id,
            allowed_from=("published",),
            status=back,
            published_at=None,
            published_by=None,
        )
        await stamp_sent(tx.session, unsent, at=None, by=None)
        tx.record(
            "binder.publish_undone",
            target=Target("binder", binder.id),
            after=Ref(grant=grant, items=len(unsent)),
            scope=_scope(binder),
        )
        for item_id in unsent:
            tx.record(
                "request_item.send_undone",
                target=Target("request_item", item_id),
                after=Ref(binder_id=binder.id, grant=grant),
                scope=_scope(binder),
            )
    return await _view(ctx, binder_id)


def _uuid_of(value: object) -> UUID | None:
    try:
        return UUID(str(value))
    except ValueError:
        return None


async def unpublish_binder(ctx: AuthContext, binder_id: UUID, reason: str) -> BinderView:
    """Published (or Complete) to Unpublished, with a reason (AC-7): client principals get 404
    for the binder and its requests at once. The reason is sealed; the audit keeps its
    fingerprint only."""
    _human(ctx, "binder.publish")
    reason = reason.strip()
    if not reason:
        raise ReasonRequired
    async with uow(ctx.tenant) as tx:
        binder, _ref, _resource = await _locked(
            tx, ctx, binder_id, "binder.publish", reason=reason
        )
        if binder.status not in ("published", "complete"):
            raise BinderNotPublished(facts={"status": binder.status})
        now = await clock.now(ctx.tenant)
        if binder.published_at is not None and now < binder.published_at + UNDO_WINDOW:
            published = await _last_ref(tx.session, binder.id, "binder.published")
            grant = _uuid_of(published.get("grant")) if published else None
            if grant is not None:
                await void_grant(tx, grant)  # unpublished inside the window: no email either
        sealed = await seal(ctx.tenant_id, reason.encode(), _reason_context(binder.id))
        await set_binder(
            tx.session,
            binder.id,
            allowed_from=("published", "complete"),
            status="unpublished",
            unpublished_at=now,
            unpublished_by=ctx.user_id,
            unpublish_reason_sealed=sealed,
        )
        tx.record(
            "binder.unpublished",
            target=Target("binder", binder.id),
            after=Ref(reason=hashlib.sha256(reason.encode()).hexdigest()),
            scope=_scope(binder),
        )
        tx.emit(BinderUnpublished(binder_id=binder.id, engagement_id=binder.engagement_id))
    return await _view(ctx, binder_id)


# --- Recipients ---------------------------------------------------------------------------------


async def set_recipients(
    ctx: AuthContext, binder_id: UUID, contact_ids: Sequence[UUID]
) -> BinderView:
    """Who the binder is for: the engagement's client's contacts. Insert-only history: an addition
    is a row, a removal is a new row with `removed_at`."""
    _human(ctx, "binder.update")
    wanted = list(dict.fromkeys(contact_ids))
    async with uow(ctx.tenant) as tx:
        binder, _ref, _resource = await _locked(tx, ctx, binder_id, "binder.update")
        if binder.status == "closed":
            raise BinderNotDraft(facts={"status": binder.status})
        known = await client_contact_names(ctx.tenant, binder.engagement_id, wanted)
        if len(known) != len(wanted):
            raise NotFound("contact")
        current = current_recipients(await recipient_rows(tx.session, binder.id))
        now = await clock.now(ctx.tenant)
        added = [c for c in wanted if c not in current]
        removed = [c for c in current if c not in wanted]
        await insert_recipient_rows(
            tx.session,
            [
                {
                    "tenant_id": ctx.tenant_id,
                    "binder_id": binder.id,
                    "contact_id": contact,
                    "added_by": ctx.user_id,
                    "removed_at": at,
                }
                for contacts, at in ((added, None), (removed, now))
                for contact in contacts
            ],
        )
        tx.record(
            "binder.recipients_changed",
            target=Target("binder", binder.id),
            after=Ref(added=len(added), removed=len(removed), recipients=len(wanted)),
            scope=_scope(binder),
        )
    return await _view(ctx, binder_id)


# --- The client's mark-done ---------------------------------------------------------------------


async def mark_done(ctx: AuthContext, binder_id: UUID) -> MarkedDoneView:
    """The client: Published to Complete, with the requests still open at that moment (OQ-8: it
    blocks nothing). A binder the client can't see answers 404 (INV-4)."""
    _human(ctx, "binder.mark_done")
    async with uow(ctx.tenant) as tx:
        binder, _ref, _resource = await _locked(tx, ctx, binder_id, "binder.mark_done")
        refuse_closed(ctx, binder, missing="binder")  # ED-118: read-only (DEC-461)
        if binder.status != "published":
            raise BinderNotPublished(facts={"status": binder.status})
        items = await binder_items(tx.session, binder.id)
        open_count = sum(1 for i in items if i.client_visible and i.status not in DONE)
        now = await clock.now(ctx.tenant)
        await set_binder(
            tx.session,
            binder.id,
            allowed_from=("published",),
            status="complete",
            marked_done_at=now,
            marked_done_by=ctx.user_id,
        )
        # P-06-T11: the index's last client activity is this act (BND-01 "Last client activity").
        await touch_client_activity(
            tx.session,
            tenant_id=ctx.tenant_id,
            binder_id=binder.id,
            work_item_id=binder.work_item_id,
            status="complete",
            at=now,
        )
        tx.record(
            "binder.marked_done",
            target=Target("binder", binder.id),
            after=Ref(open=open_count),
            scope=_scope(binder),
        )
        tx.emit(
            BinderMarkedDone(
                binder_id=binder.id, engagement_id=binder.engagement_id, open_count=open_count
            )
        )
    return MarkedDoneView(binder_id, "complete", now, open_count)


async def firm_acted_since(
    session: AsyncSession, items: Sequence[RequestItem], since: datetime
) -> bool:
    """Whether the firm sent, waived or returned a request of the binder after `since` (DEC-24:
    a client's Undo of Mark as Done closes then): the requests' own stamps, and the audit trail
    for every such act, however many other events there are (DEC-334)."""
    if any(i.sent_at is not None and i.sent_at > since for i in items):
        return True
    if any(i.na_at is not None and i.na_at > since for i in items):
        return True
    return await audit_acted_since(
        session, [("request_item", i.id) for i in items], sorted(FIRM_ITEM_ACTS), since
    )


async def undo_mark_done(ctx: AuthContext, binder_id: UUID) -> MarkDoneUndoneView:
    """R-01-T08: the client's Undo of Mark as Done, a compensating event (DEC-24, DEC-334): the
    `binder.marked_done` event stays, `binder.mark_done_undone` is appended and the binder is
    Published again with its mark-done stamps cleared (BND-02's "Marked done by …" goes). Open
    until the firm sends, waives or returns a request of the binder (409 `firm_already_acted`);
    the marker's own (403 for another person); once (409 `nothing_to_undo`)."""
    _human(ctx, "binder.mark_done")
    async with uow(ctx.tenant) as tx:
        binder, _ref, _resource = await _locked(tx, ctx, binder_id, "binder.mark_done")
        refuse_closed(ctx, binder, missing="binder")  # ED-118: read-only (DEC-461)
        if binder.status == "published" and binder.marked_done_at is None:
            raise NothingToUndo(facts={"binder_id": str(binder.id)})
        if binder.status != "complete" or binder.marked_done_at is None:
            raise FirmAlreadyActed(facts={"binder_id": str(binder.id)})
        if binder.marked_done_by != ctx.user_id:
            raise Forbidden("binder.mark_done", "role")
        # Every request row of the binder, locked: a firm act in flight on one of them (each
        # takes its request's lock) commits first and is then seen here, or waits for this Undo.
        items = await binder_items(tx.session, binder.id, lock=True)
        if await firm_acted_since(tx.session, items, binder.marked_done_at):
            raise FirmAlreadyActed(facts={"binder_id": str(binder.id)})
        now = await clock.now(ctx.tenant)
        await set_binder(
            tx.session,
            binder.id,
            allowed_from=("complete",),
            status="published",
            marked_done_at=None,
            marked_done_by=None,
        )
        await touch_client_activity(
            tx.session,
            tenant_id=ctx.tenant_id,
            binder_id=binder.id,
            work_item_id=binder.work_item_id,
            status="published",
            at=now,
        )
        tx.record(
            "binder.mark_done_undone", target=Target("binder", binder.id), scope=_scope(binder)
        )
        tx.emit(BinderMarkDoneUndone(binder_id=binder.id, engagement_id=binder.engagement_id))
        open_count = sum(1 for i in items if i.client_visible and i.status not in DONE)
    return MarkDoneUndoneView(binder.id, "tonal" if open_count else "ready", now)


# --- Close on C1 --------------------------------------------------------------------------------

# A terminal status of the work (C1) -> the close rule code recorded on the binder (OQ-2). Kinds
# with their own terminal facts register theirs (T-02: "e-file accepted" on a tax return).
_CLOSE_RULES: dict[str, str] = {"delivered": "work_delivered", "archived": "work_archived"}
_SYSTEM_ACTOR: Final = "requests.binder_close"


def register_binder_close_rule(status: str, rule_code: str) -> None:
    """A terminal status that closes binders, and the rule code it records."""
    known = _CLOSE_RULES.get(status)
    if known is not None and known != rule_code:
        raise ValueError(f"status {status!r} already closes binders as {known!r}")
    _CLOSE_RULES[status] = rule_code


async def close_on_status_changed(event: OutboxEvent) -> None:
    """C1's `work_item.status_changed` (or `engagement.status_changed`) into a terminal status:
    close the binders not yet closed on it (Story 1.5), audited `binder.closed` as the system."""
    rule = _CLOSE_RULES.get(str(event.payload.get("to_status")))
    if rule is None:
        return
    work_item = (
        _uuid_of(event.payload.get("work_item_id")) if "work_item_id" in event.payload else None
    )
    engagement = (
        _uuid_of(event.payload.get("engagement_id")) if "engagement_id" in event.payload else None
    )
    tenant = TenantContext(event.tenant_id, "system", _SYSTEM_ACTOR)
    if not await flag_enabled(tenant, BINDERS_ENGINE):
        return
    async with tenant_session(tenant) as session:
        pending = await open_binders(session, engagement_id=engagement, work_item_id=work_item)
    if not pending:
        return
    # Closed meanwhile by another delivery of the event: nothing left to write.
    with suppress(MissingAuditEvent):
        await _close(tenant, engagement, work_item, rule)


async def _close(
    tenant: TenantContext, engagement: UUID | None, work_item: UUID | None, rule: str
) -> None:
    async with uow(tenant) as tx:
        now = await clock.now(tenant)
        for binder in await open_binders(
            tx.session, engagement_id=engagement, work_item_id=work_item
        ):
            await set_binder(
                tx.session,
                binder.id,
                allowed_from=("draft", "published", "unpublished", "complete"),
                status="closed",
                closed_at=now,
                closed_reason=rule,
            )
            tx.record("binder.closed", target=Target("binder", binder.id), scope=_scope(binder))
            tx.emit(BinderClosed(binder_id=binder.id, engagement_id=binder.engagement_id))


SUBSCRIPTIONS: dict[str, Callable[[OutboxEvent], Awaitable[None]]] = {
    "work_item.status_changed": close_on_status_changed,
    "engagement.status_changed": close_on_status_changed,
}


# --- R-01-T09: the binder a portal drop lands in -----------------------------------------------


@dataclass(frozen=True)
class DropBinder:
    binder_id: UUID
    engagement_id: UUID
    resource: Resource  # the engagement, with the binder's client facts


async def drop_binder(ctx: AuthContext, binder_id: UUID, action: str) -> DropBinder:
    """The published binder a client drops into, authorised for `action` with its client facts
    (a client admin in scope; a contributor with a request of it assigned). A binder out of the
    caller's scope, a draft, a forged id or a binder no longer open answers 404 (INV-4)."""
    binder, _ref, resource = await _readable(ctx, binder_id, action)
    if binder.status != "published":
        raise NotFound("binder")
    return DropBinder(binder.id, binder.engagement_id, resource)


async def drop_binder_open(tenant: TenantContext, binder_id: UUID) -> UUID | None:
    """For the system sort: the binder's engagement while it is published, else None."""
    async with tenant_session(tenant) as session:
        binder = await get_binder(session, binder_id)
    return binder.engagement_id if binder is not None and binder.status == "published" else None
