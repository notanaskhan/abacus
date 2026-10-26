"""Request lifecycle v2 (P-06-T10; SPEC-319 AC-11 to AC-14; C5 v1). PROTECTED.

One request's moves, each a person's (INV-1) except the client's Ignore:
- edit any non-terminal request (PATCH), and delete a never-sent Draft (soft; a sent one is 409
  `request_already_sent`);
- send: Draft to Requested. It needs a due date (its own or the binder's), its client wording
  must pass `communications`' scope check (409 `out_of_scope`, nothing sent), and unchanged
  model-drafted wording is refused while the firm's P-25 setting is off, which it is for every
  firm until N-03 (409 `model_text_not_permitted`, DV-11, DEC-79). The client's email is held by
  an approval grant until the 10-s Undo window ends (ADR-161), exactly as a binder's publish;
- waive to Not applicable with a reason; the client's Ignore (status stays `requested`, OQ-3)
  and the firm's return to client, which clears it; incorporate (`pending_incorporation` to
  `incorporated`);
- delegate: a client contact who is a portal user gets a `request_item` grant on this request
  only (P-09);
- upload intents (R-01's 90-second hint) and the live poll BND-02 reads every 5 s.
"""

from __future__ import annotations

import hashlib
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Final
from uuid import UUID

from abacus.kernel import clock
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.listing import Position, clamp_limit, decode_cursor, encode_cursor, query_hash
from abacus.kernel.uow import (
    Ref,
    Scope,
    Target,
    UnitOfWork,
    audit_of_targets,
    audit_total_of_targets,
    event_sha256,
    uow,
)
from abacus.modules.engagements.api import (
    EngagementRef,
    client_of,
    contact_portal_user,
    get_ref,
    holds_tax_return,
    lock_ref,
)
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    ItemFacts,
    Resource,
    ScopeFacts,
    allowed_actions,
    authorise,
    consent_given,
    grant_client_access,
    issue_grant,
    void_grant,
)
from abacus.modules.requests import comments
from abacus.modules.requests.binders import (
    GRANT_LIFETIME,
    UNDO_WINDOW,
    ActivityPage,
    DueDateRequired,
    EffectStarted,
    UndoWindowClosed,
    activity_view,
    check_action,
)
from abacus.modules.requests.client_undo import (
    IGNORE_NOTES_PER_REQUEST,
    UNDO_REASON,
    UNDOABLE_ITEM,
    FirmAlreadyActed,
    IgnoreNotesExhausted,
    NothingToUndo,
)
from abacus.modules.requests.events import RequestItemIgnoreUndone, RequestItemSent
from abacus.modules.requests.models import RequestItem
from abacus.modules.requests.repository import (
    binder_items,
    end_delegations,
    get_binder,
    get_request_item,
    ignore_note_count,
    insert_client_response,
    insert_delegation,
    insert_upload_intent,
    is_delegated,
    live_upload_intents,
    newest_response,
    open_delegations,
    set_item_fields,
    stamp_sent,
)
from abacus.modules.requests.service import reclassify_described

TERMINAL: Final = frozenset({"received", "not_applicable"})
NA_REASONS: Final = ("not_applicable_this_year", "already_sent", "dont_have", "firm_waived")
IGNORE_REASONS: Final = ("not_this_year", "sent_another_way", "dont_have")
_ITEM_ACTIONS: Final = (
    "request_item.update",
    "request_item.send",
    "request_item.waive",
    "request_item.return",
    "request_item.delegate",
    "activity.read",
)


class RequestAlreadySent(DomainConflict):
    """Only a Draft never sent can be deleted or sent; this one was sent."""

    code = "request_already_sent"


class RequestClosed(DomainConflict):
    """The request is Received or Not applicable: reopen it before changing it."""

    code = "request_closed"


class OutOfScope(DomainConflict):
    """The client wording names something outside the engagement; nothing was sent."""

    code = "out_of_scope"


class ModelTextNotPermitted(DomainConflict):
    """Unchanged model-drafted client wording can't be sent while the firm's P-25 is off."""

    code = "model_text_not_permitted"


class NotIgnored(DomainConflict):
    """Only a request the client ignored can be returned to them."""

    code = "not_ignored"


class NotPendingIncorporation(DomainConflict):
    """Only a request pending incorporation can be marked incorporated."""

    code = "not_pending_incorporation"


@dataclass(frozen=True)
class RequestItemV2View:
    item: RequestItem
    binder_id: UUID | None
    undo_until: datetime | None
    allowed_actions: list[str]


def _facts(item: RequestItem) -> ItemFacts:
    return ItemFacts(item.client_visible, item.client_assignee_user_id)


def _scope(item: RequestItem) -> Scope:
    return Scope(engagement_id=item.engagement_id)


def _human(ctx: AuthContext, action: str) -> None:
    """INV-1: a person's own decision, never an agent, the platform or a support session."""
    if ctx.tenant.actor_kind != "human" or ctx.is_support:
        raise Forbidden(action, "role")


async def _locked(
    tx: UnitOfWork,
    ctx: AuthContext,
    engagement_id: UUID,
    item_id: UUID,
    action: str,
    *,
    reason: str | None = None,
) -> tuple[RequestItem, EngagementRef, Resource]:
    """The request, row-locked for one move and authorised against the same rows; a deleted
    one, or one of another engagement, is not found."""
    item = await get_request_item(tx.session, item_id, lock=True)
    if item is None or item.engagement_id != engagement_id or item.deleted_at is not None:
        raise NotFound("request_item")
    ref = await lock_ref(tx, engagement_id)
    resource = Resource.engagement(
        ref.tenant_id, ref.id, archived=ref.archived, client_id=ref.client_id, item=_facts(item)
    )
    await authorise(ctx, action, resource, reason=reason)
    return item, ref, resource


async def check_item_action(
    ctx: AuthContext, engagement_id: UUID, item_id: UUID, action: str
) -> None:
    """Authorise `action` on the request (read-only), so a replayed send or return is checked
    like the first one (ED-023): the stored answer reaches only someone who may act now."""
    async with tenant_session(ctx.tenant) as session:
        item = await get_request_item(session, item_id)
    if item is None or item.engagement_id != engagement_id or item.deleted_at is not None:
        raise NotFound("request_item")
    ref = await get_ref(ctx, engagement_id)
    await authorise(
        ctx,
        action,
        Resource.engagement(
            ref.tenant_id,
            ref.id,
            archived=ref.archived,
            client_id=ref.client_id,
            item=_facts(item),
        ),
    )


def _fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


async def view(ctx: AuthContext, engagement_id: UUID, item_id: UUID) -> RequestItemV2View:
    async with tenant_session(ctx.tenant) as session:
        item = await get_request_item(session, item_id)
        if item is None or item.engagement_id != engagement_id or item.deleted_at is not None:
            raise NotFound("request_item")
        binder = await get_binder(session, item.request_list_id)
    ref = await get_ref(ctx, engagement_id)
    ref_resource = Resource.engagement(
        ref.tenant_id, ref.id, archived=ref.archived, client_id=ref.client_id, item=_facts(item)
    )
    await authorise(ctx, "request_item.read", ref_resource)
    now = await clock.now(ctx.tenant)
    undo_until = None
    if item.sent_at is not None and now < item.sent_at + UNDO_WINDOW:
        undo_until = item.sent_at + UNDO_WINDOW
    actions = sorted(await allowed_actions(ctx, ref_resource, _ITEM_ACTIONS))
    return RequestItemV2View(item, binder.id if binder else None, undo_until, actions)


# --- edits ---------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ItemPatch:
    """Absent (None) fields are unchanged. `set_fields` names the ones the caller sent."""

    values: dict[str, object]


_EDITABLE: Final = frozenset(
    {"title", "description", "category_id", "period_start", "period_end", "due_on", "wave"}
    | {"client_assignee_user_id", "firm_owner_user_id", "supports_ref", "linked_ref"}
)


async def update_item(
    ctx: AuthContext, engagement_id: UUID, item_id: UUID, patch: ItemPatch
) -> None:
    unknown = set(patch.values) - _EDITABLE
    if unknown:
        raise ValueError(f"not editable: {sorted(unknown)}")
    async with uow(ctx.tenant) as tx:
        item, _ref, _resource = await _locked(
            tx, ctx, engagement_id, item_id, "request_item.update"
        )
        if item.status in TERMINAL:
            raise RequestClosed(facts={"status": item.status})
        changed = {k: v for k, v in patch.values.items() if getattr(item, k) != v}
        if not changed:
            return
        await set_item_fields(tx.session, item.id, changed)
        if "description" in changed:
            await reclassify_described(tx, item, str(changed["description"]))
        tx.record(
            "request_item.updated",
            target=Target("request_item", item.id),
            after=Ref(**dict.fromkeys(sorted(changed), 1)),
            scope=_scope(item),
        )


async def delete_item(ctx: AuthContext, engagement_id: UUID, item_id: UUID) -> datetime:
    """A never-sent Draft only (AC-13); soft, kept for the audit trail."""
    async with uow(ctx.tenant) as tx:
        item, _ref, _resource = await _locked(
            tx, ctx, engagement_id, item_id, "request_item.update"
        )
        if item.status != "draft" or item.sent_at is not None:
            raise RequestAlreadySent(facts={"status": item.status})
        now = await clock.now(ctx.tenant)
        await set_item_fields(tx.session, item.id, {"deleted_at": now, "deleted_by": ctx.user_id})
        tx.record(
            "request_item.deleted", target=Target("request_item", item.id), scope=_scope(item)
        )
    return now


# --- send and its Undo ---------------------------------------------------------------------------


async def send_item(ctx: AuthContext, engagement_id: UUID, item_id: UUID) -> None:
    _human(ctx, "request_item.send")
    async with uow(ctx.tenant) as tx:
        item, ref, resource = await _locked(tx, ctx, engagement_id, item_id, "request_item.send")
        if item.status != "draft" or item.sent_at is not None:
            raise RequestAlreadySent(facts={"status": item.status})
        binder = await get_binder(tx.session, item.request_list_id)
        if item.due_on is None and (binder is None or binder.default_due_on is None):
            raise DueDateRequired(facts={"count": 1, "request_item_0": str(item.id)})
        # DV-11 (DEC-79): P-25 is off for every firm until N-03, so unchanged model text never
        # reaches a client.
        if (
            item.drafted_wording_source == "model"
            and item.drafted_wording_fingerprint == _fingerprint(item.description)
        ):
            raise ModelTextNotPermitted
        check = comments.scope_check()
        if check is None:
            raise comments.SharingUnavailable
        wording = "\n".join(t for t in (item.title, item.description) if t)
        if await check(ctx, ref, wording):
            raise OutOfScope
        now = await clock.now(ctx.tenant)
        await set_item_fields(tx.session, item.id, {"client_visible": True})
        await stamp_sent(tx.session, [item.id], at=now, by=ctx.user_id)
        event = RequestItemSent(
            request_item_id=item.id, engagement_id=item.engagement_id, sent_by=ctx.user_id
        )
        undo_until = now + UNDO_WINDOW
        grant = await issue_grant(
            tx,
            ctx,
            action="request_item.send",
            resource=resource,
            subject=Target("request_item", item.id),
            payload_sha256=event_sha256(event),
            not_before=undo_until,
            expires_at=undo_until + GRANT_LIFETIME,
        )
        tx.emit(event, not_before=undo_until, grant_id=grant)
        tx.record(
            "request_item.sent",
            target=Target("request_item", item.id),
            after=Ref(grant=grant),
            scope=_scope(item),
        )


async def undo_send(ctx: AuthContext, engagement_id: UUID, item_id: UUID) -> None:
    """Within 10 s of a send: void its grant (no email leaves) and put the request back as a
    Draft. Later, 409 `undo_window_closed`; once delivery consumed the grant, 409
    `effect_started`."""
    _human(ctx, "request_item.send")
    async with uow(ctx.tenant) as tx:
        item, _ref, _resource = await _locked(tx, ctx, engagement_id, item_id, "request_item.send")
        now = await clock.now(ctx.tenant)
        if (
            item.sent_at is None
            or item.sent_by != ctx.user_id
            or now >= item.sent_at + UNDO_WINDOW
        ):
            raise UndoWindowClosed
        sent = await audit_of_targets(
            tx.session, [("request_item", item.id)], None, 1, action="request_item.sent"
        )
        grant = _uuid(sent[0].after_ref.get("grant")) if sent and sent[0].after_ref else None
        if grant is None or not await void_grant(tx, grant):
            raise EffectStarted
        await set_item_fields(tx.session, item.id, {"client_visible": False})
        await stamp_sent(tx.session, [item.id], at=None, by=None)
        tx.record(
            "request_item.send_undone",
            target=Target("request_item", item.id),
            after=Ref(grant=grant),
            scope=_scope(item),
        )


def _uuid(value: object) -> UUID | None:
    try:
        return UUID(str(value))
    except ValueError:
        return None


# --- waive, ignore, return, incorporate ----------------------------------------------------------


async def waive_item(
    ctx: AuthContext, engagement_id: UUID, item_id: UUID, na_reason: str, note: str
) -> None:
    async with uow(ctx.tenant) as tx:
        item, _ref, _resource = await _locked(
            tx, ctx, engagement_id, item_id, "request_item.waive", reason=na_reason
        )
        if item.status in TERMINAL:
            raise RequestClosed(facts={"status": item.status})
        now = await clock.now(ctx.tenant)
        await set_item_fields(
            tx.session,
            item.id,
            {
                "status": "not_applicable",
                "na_reason": na_reason,
                "na_note": note,
                "na_by": ctx.user_id,
                "na_at": now,
            },
        )
        tx.record(
            "request_item.waived",
            target=Target("request_item", item.id),
            after=Ref(reason=NA_REASONS.index(na_reason)),
            scope=_scope(item),
        )


async def ignore_item(ctx: AuthContext, item_id: UUID, reason: str, note: str | None) -> datetime:
    """The client's Ignore (AC-12): the reason is a SPEC-042 response, the status stays
    `requested`, and `client_ignored_at` is stamped until the firm returns or waives it. R-01-T08:
    the optional note is a shared client comment on the request with origin `ignore_note`
    (sealed, insert-only, ADR-109), never copied into the response row, so the firm reads it in
    the thread and an Undo of the Ignore leaves it there."""
    body = comments.clean_text(note, comments.MAX_BODY) if note is not None else None
    async with uow(ctx.tenant) as tx:
        item = await get_request_item(tx.session, item_id, lock=True)
        if item is None or item.deleted_at is not None:
            raise NotFound("request_item")
        ref = await lock_ref(tx, item.engagement_id)
        resource = Resource.engagement(
            ref.tenant_id,
            ref.id,
            archived=ref.archived,
            client_id=ref.client_id,
            item=_facts(item),
        )
        try:
            await authorise(ctx, "request_item.ignore", resource, reason=reason)
            if body is not None:  # the note is a shared comment: the client must be able to post
                await authorise(ctx, "comment.create", resource)
        except Forbidden:
            raise NotFound("request_item") from None  # INV-4: not theirs, so not there
        if await is_delegated(tx.session, item.id):
            raise NotFound("request_item")  # it went to its third party directly (INV-4)
        if item.status not in ("requested", "returned"):
            raise RequestClosed(facts={"status": item.status})
        if (
            body is not None
            and await ignore_note_count(tx.session, item.id) >= IGNORE_NOTES_PER_REQUEST
        ):
            raise IgnoreNotesExhausted(facts={"request_item_id": str(item.id)})
        now = await clock.now(ctx.tenant)
        await insert_client_response(
            tx.session,
            tenant_id=ctx.tenant_id,
            engagement_id=item.engagement_id,
            request_item_id=item.id,
            kind="not_applicable",
            reason=reason,
            note=None,
            by_user=ctx.user_id,
        )
        await set_item_fields(tx.session, item.id, {"client_ignored_at": now})
        tx.record(
            "request_item.ignored",
            target=Target("request_item", item.id),
            after=Ref(reason=IGNORE_REASONS.index(reason)),
            scope=_scope(item),
        )
        if body is not None:
            comment_id = await comments.insert_ignore_note(
                tx, ctx, item.engagement_id, item.id, body
            )
            tx.record(
                "request_item.ignore_note_added",
                target=Target("request_item", item.id),
                after=Ref(comment=comment_id),
                scope=_scope(item),
            )
    return now


async def check_ignore(ctx: AuthContext, item_id: UUID) -> None:
    """Authorise `request_item.ignore` on the request (read-only), so a replayed Undo is checked
    like the first one (ED-023); not the caller's to see: 404 (INV-4)."""
    async with tenant_session(ctx.tenant) as session:
        item = await get_request_item(session, item_id)
    if item is None or item.deleted_at is not None:
        raise NotFound("request_item")
    ref = await get_ref(ctx, item.engagement_id)
    try:
        await authorise(
            ctx,
            "request_item.ignore",
            Resource.engagement(
                ref.tenant_id,
                ref.id,
                archived=ref.archived,
                client_id=ref.client_id,
                item=_facts(item),
            ),
            reason=UNDO_REASON,
        )
    except Forbidden:
        raise NotFound("request_item") from None


async def undo_ignore(ctx: AuthContext, item_id: UUID) -> datetime:
    """R-01-T08: the client's Undo of their Ignore, a compensating event (DEC-24, DEC-334): the
    Ignore's own rows stay, a `withdrawn` SPEC-042 response is appended, `client_ignored_at` is
    cleared and the request reads To do again. Open until the firm acts on the request (409
    `firm_already_acted`); the ignorer's own (403 for another person); once (409
    `nothing_to_undo`). Not theirs to see: 404 (INV-4)."""
    async with uow(ctx.tenant) as tx:
        item = await get_request_item(tx.session, item_id, lock=True)
        if item is None or item.deleted_at is not None:
            raise NotFound("request_item")
        ref = await lock_ref(tx, item.engagement_id)
        resource = Resource.engagement(
            ref.tenant_id,
            ref.id,
            archived=ref.archived,
            client_id=ref.client_id,
            item=_facts(item),
        )
        try:
            await authorise(ctx, "request_item.ignore", resource, reason=UNDO_REASON)
        except Forbidden:
            raise NotFound("request_item") from None  # INV-4: not theirs, so not there
        if await is_delegated(tx.session, item.id):
            raise NotFound("request_item")  # delegated since: the client's no longer (INV-4)
        response = await newest_response(tx.session, item.id)
        if response is None or response.kind != "not_applicable":
            raise NothingToUndo(facts={"request_item_id": str(item.id)})
        if response.by_user != ctx.user_id:
            raise Forbidden("request_item.ignore", "role")
        if item.status not in UNDOABLE_ITEM or item.client_ignored_at is None:
            raise FirmAlreadyActed(facts={"request_item_id": str(item.id)})
        now = await clock.now(ctx.tenant)
        await insert_client_response(
            tx.session,
            tenant_id=ctx.tenant_id,
            engagement_id=item.engagement_id,
            request_item_id=item.id,
            kind="withdrawn",
            reason=None,
            note=None,
            by_user=ctx.user_id,
        )
        await set_item_fields(tx.session, item.id, {"client_ignored_at": None})
        tx.record(
            "request_item.ignore_undone",
            target=Target("request_item", item.id),
            scope=_scope(item),
        )
        tx.emit(RequestItemIgnoreUndone(request_item_id=item.id, engagement_id=item.engagement_id))
    return now


async def return_to_client(ctx: AuthContext, engagement_id: UUID, item_id: UUID) -> None:
    """The firm returns an ignored request (AC-12): the Ignore is cleared, the request stays
    asked. The client hears of it with the next follow-up (P-06-T14)."""
    _human(ctx, "request_item.return")
    async with uow(ctx.tenant) as tx:
        item, _ref, _resource = await _locked(
            tx, ctx, engagement_id, item_id, "request_item.return"
        )
        if item.client_ignored_at is None:
            raise NotIgnored
        await set_item_fields(tx.session, item.id, {"client_ignored_at": None})
        tx.record(
            "request_item.returned_to_client",
            target=Target("request_item", item.id),
            scope=_scope(item),
        )


async def incorporate_item(ctx: AuthContext, engagement_id: UUID, item_id: UUID) -> None:
    async with uow(ctx.tenant) as tx:
        item, _ref, _resource = await _locked(
            tx, ctx, engagement_id, item_id, "request_item.update"
        )
        if item.incorporation_state != "pending_incorporation":
            raise NotPendingIncorporation(facts={"state": item.incorporation_state})
        now = await clock.now(ctx.tenant)
        await set_item_fields(
            tx.session,
            item.id,
            {
                "incorporation_state": "incorporated",
                "incorporated_by": ctx.user_id,
                "incorporated_at": now,
            },
        )
        tx.record(
            "request_item.incorporated", target=Target("request_item", item.id), scope=_scope(item)
        )


# --- delegation ----------------------------------------------------------------------------------


@dataclass(frozen=True)
class DelegationView:
    request_item_id: UUID
    contact_id: UUID
    grant_id: UUID
    granted_by: UUID
    granted_at: datetime


class ContactNotPortalUser(DomainConflict):
    """The contact has no portal sign-in yet: invite them first, then delegate."""

    code = "contact_not_portal_user"


class ConsentRequired(DomainConflict):
    """§7216 (ADR P-12, R-01-T13): a request of an engagement that holds a tax return goes to a
    third party only under the client's `third_party_disclosure` consent (C19). Until T-01
    registers that consent nobody holds it, so such a delegation is refused (fail closed)."""

    code = "consent_required"


THIRD_PARTY_DISCLOSURE: Final = "third_party_disclosure"


async def third_party_consented(tenant: TenantContext, engagement_id: UUID) -> bool:
    """Whether the engagement's requests may go to a third party: always outside tax work; on an
    engagement holding a `tax_return` work item, only under the client's consent (DEC-388)."""
    if not await holds_tax_return(tenant, engagement_id):
        return True
    client = await client_of(tenant, engagement_id)
    return client is not None and await consent_given(
        tenant, client, THIRD_PARTY_DISCLOSURE, await clock.now(tenant)
    )


async def _consented(tenant: TenantContext, engagement_id: UUID) -> None:
    if not await third_party_consented(tenant, engagement_id):
        raise ConsentRequired(facts={"engagement_id": str(engagement_id)})


async def delegate_item(
    ctx: AuthContext, engagement_id: UUID, item_id: UUID, contact_id: UUID
) -> DelegationView:
    """A client contact gets this one request (P-09 `request_item` grant, role `delegate`)."""
    _human(ctx, "request_item.delegate")
    async with tenant_session(ctx.tenant) as session:
        item = await get_request_item(session, item_id)
        if item is None or item.engagement_id != engagement_id or item.deleted_at is not None:
            raise NotFound("request_item")
    ref = await get_ref(ctx, engagement_id)
    resource = Resource.engagement(
        ref.tenant_id, ref.id, archived=ref.archived, client_id=ref.client_id, item=_facts(item)
    )
    await authorise(ctx, "request_item.delegate", resource)
    await _consented(ctx.tenant, engagement_id)  # before any grant exists (DEC-388)
    contact = await contact_portal_user(ctx.tenant, engagement_id, contact_id)
    if contact is None:
        raise ContactNotPortalUser
    grant = await grant_client_access(
        ctx,
        resource,
        user_id=contact,
        role="delegate",
        scope_kind="request_item",
        scope_id=item.id,
        contact_id=contact_id,
        action="request_item.delegate",
    )
    now = await clock.now(ctx.tenant)
    async with uow(ctx.tenant) as tx:
        # The request's lock: a client's Ignore or its Undo in flight either commits first or
        # waits and then finds the delegation (R-01-T08).
        if await get_request_item(tx.session, item.id, lock=True) is None:
            raise NotFound("request_item")
        await insert_delegation(
            tx.session,
            tenant_id=ctx.tenant_id,
            request_item_id=item.id,
            contact_id=contact_id,
            grant_id=grant,
            granted_by=ctx.user_id,
        )
        tx.record(
            "request_item.delegated",
            target=Target("request_item", item.id),
            after=Ref(grant=grant),
            scope=_scope(item),
        )
    return DelegationView(item.id, contact_id, grant, ctx.user_id, now)


# --- a contact's delegated requests (P-07-T25, C5; DEC-300) --------------------------------------


async def record_contact_delegations(
    tx: UnitOfWork, contact_id: UUID, delegated: Sequence[tuple[UUID, UUID]], by: UUID
) -> None:
    """In the inviting unit of work: each (grant, request item) a contact invitation limits the
    contact to becomes a delegation. organisations has checked the items are the contact's
    client's and identity has authorised the grants."""
    for grant_id, item_id in delegated:
        item = await get_request_item(tx.session, item_id, lock=True)  # as `delegate_item`
        if item is None or item.deleted_at is not None:
            raise NotFound("request_item")
        # §7216 (DEC-388): the invitation's unit of work rolls back, so no grant, invitation or
        # email exists for a tax request without the client's consent.
        await _consented(
            TenantContext(item.tenant_id, "system", "requests:delegate"), item.engagement_id
        )
        await insert_delegation(
            tx.session,
            tenant_id=item.tenant_id,
            request_item_id=item.id,
            contact_id=contact_id,
            grant_id=grant_id,
            granted_by=by,
        )
        tx.record(
            "request_item.delegated",
            target=Target("request_item", item.id),
            after=Ref(grant=grant_id),
            scope=_scope(item),
        )


async def end_contact_delegations(tx: UnitOfWork, grant_ids: Sequence[UUID]) -> list[UUID]:
    """The delegations under these grants end; the requests stay with the client (they are
    never reassigned or deleted). The request items whose delegation ended."""
    ended = await end_delegations(tx.session, grant_ids)
    for item_id, engagement_id in ended:
        tx.record(
            "request_item.delegation_ended",
            target=Target("request_item", item_id),
            scope=Scope(engagement_id=engagement_id),
        )
    return [item_id for item_id, _ in ended]


async def contact_delegations(
    tenant: TenantContext, contact_ids: Sequence[UUID]
) -> dict[UUID, tuple[tuple[UUID, ...], tuple[UUID, ...]]]:
    """CLI-04's delegated column and footer: per contact, the requests delegated to them now and
    those of them the firm has received."""
    async with tenant_session(tenant) as session:
        rows = await open_delegations(session, contact_ids)
    items: dict[UUID, dict[UUID, bool]] = {}
    for contact, item, status in rows:
        items.setdefault(contact, {})[item] = status == "received"
    return {
        c: (tuple(found), tuple(i for i, received in found.items() if received))
        for c, found in items.items()
    }


# --- upload intents and the live poll ------------------------------------------------------------


async def announce_upload(ctx: AuthContext, item_id: UUID, files_expected: int) -> datetime:
    """R-01's 90-second hint that an upload is under way (UNLOGGED, never authoritative)."""
    async with uow(ctx.tenant) as tx:
        item = await get_request_item(tx.session, item_id)
        if item is None or item.deleted_at is not None:
            raise NotFound("request_item")
        ref = await lock_ref(tx, item.engagement_id)
        resource = Resource.engagement(
            ref.tenant_id,
            ref.id,
            archived=ref.archived,
            client_id=ref.client_id,
            item=_facts(item),
        )
        try:
            await authorise(ctx, "evidence.upload", resource)
        except Forbidden:
            raise NotFound("request_item") from None
        expires = await insert_upload_intent(
            tx.session,
            tenant_id=ctx.tenant_id,
            request_item_id=item.id,
            user_id=ctx.user_id,
            files_expected=files_expected,
        )
        tx.record(
            "upload_intent.announced", target=Target("request_item", item.id), scope=_scope(item)
        )
    return expires


@dataclass(frozen=True)
class LiveItem:
    request_item_id: UUID
    uploading_files: int
    inbox_waiting: int
    screening_running: bool


# evidence registers what it knows per request: (inbox files waiting, a screening running).
LiveFacts = Callable[[TenantContext, Sequence[UUID]], Awaitable[dict[UUID, tuple[int, bool]]]]
_live_facts: LiveFacts | None = None


def register_live_facts(provider: LiveFacts) -> None:
    global _live_facts
    if _live_facts is not None and (_live_facts.__module__, _live_facts.__qualname__) != (
        provider.__module__,
        provider.__qualname__,
    ):
        raise RuntimeError("the live facts provider is already registered")
    _live_facts = provider


async def binder_live(ctx: AuthContext, binder_id: UUID) -> tuple[list[LiveItem], datetime]:
    """BND-02's 5-s poll (AC-14): live upload intents, inbox files waiting and screening running,
    per request of the binder. An unregistered evidence provider reads as none (fail closed)."""
    await check_action(ctx, binder_id, "request_item.read")
    now = await clock.now(ctx.tenant)
    async with tenant_session(ctx.tenant) as session:
        items = [i.id for i in await binder_items(session, binder_id) if i.deleted_at is None]
        uploading = await live_upload_intents(session, items)
    facts = await _live_facts(ctx.tenant, items) if _live_facts is not None and items else {}
    return (
        [
            LiveItem(
                i,
                uploading.get(i, 0),
                facts.get(i, (0, False))[0],
                facts.get(i, (0, False))[1],
            )
            for i in items
        ],
        now,
    )


async def item_activity(
    ctx: AuthContext, engagement_id: UUID, item_id: UUID, cursor: str | None
) -> ActivityPage:
    """The request's audit events, newest first, identifiers only (`audit_trail`'s rows)."""
    async with tenant_session(ctx.tenant) as session:
        item = await get_request_item(session, item_id)
        if item is None or item.engagement_id != engagement_id:
            raise NotFound("request_item")
    ref = await get_ref(ctx, engagement_id)
    await authorise(
        ctx,
        "activity.read",
        Resource.engagement(ref.tenant_id, ref.id, archived=ref.archived, client_id=ref.client_id),
    )
    where = f"request_item_activity:{item.id}"
    query = query_hash(item=item.id)
    before = None
    if cursor:
        position = decode_cursor(cursor, tenant_id=ctx.tenant_id, resource=where, query=query)
        if not isinstance(position.key, int):
            raise NotFound("cursor")
        before = position.key
    size = clamp_limit(None)
    targets = [("request_item", item.id)]
    async with tenant_session(ctx.tenant) as session:
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
    return ActivityPage([activity_view(e) for e in page], following, total[0], total[1])


async def request_item_scope(tenant: TenantContext, item_id: UUID) -> ScopeFacts | None:
    """A `request_item` grant's scope (a delegate's, P-06-T10): the request, inside its
    engagement and client."""
    async with tenant_session(tenant) as session:
        item = await get_request_item(session, item_id)
    if item is None or item.deleted_at is not None:
        return None
    client = await client_of(tenant, item.engagement_id)
    return None if client is None else ScopeFacts(client, engagement_id=item.engagement_id)
