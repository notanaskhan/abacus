"""Follow-ups v2: drafted by the platform, sent by a person (P-06-T14; DEC-74, DEC-220). PROTECTED.

BND-01 b and BND-02 d: a person picks binders or requests and the platform drafts one follow-up
per client contact per engagement, from the firm's published Reminder template (C16, in the
database), listing each open client-visible request once and never one already waiting in a
draft to that contact. The composition is the Request Chaser's (`drafted_by_kind = 'agent'`,
the C-31 marker); the person who asked is the audit actor.

Only a Published binder's open requests are chased (409 `binder_not_published` for another).
Every value a client or a person wrote is scope-checked on its own, at draft and again at send:
each request title and whatever the person added (an edit, the SPEC-027 note); the fixed
template text and the portal link are platform text and are not (DEC-220). A person edits the
body (sealed; `edit_fingerprint`), then sends: human only (agent: deny, DEC-74; `follow_up.sent`
is in the human-only register), scope-checked (409 `out_of_scope`, nothing written), and held by
an approval grant until the 10-s Undo window ends (ADR-161). The SPEC-027 engagement routes send
through the same hold (`send_overdue`). The
body sent is frozen in `body_sealed`; the relay's delivery of `follow_up.sent` sends the email
through communications (COMM-001). Undo within the window voids the grant and puts the draft
back; dismiss closes it. No model text reaches a client (DEC-79, ADR-111).

SHL-20 b, the screening return (TASK-1252; C5 §12, DEC-368): drafted for one request from the
firm's published Return template, with the files it returns. Its send also returns them, in the
grant's unit of work: one `send_back` per file (evidence's, a person serving a request with
`evidence.reject`) and the request `returned`; its sender must be allowed `comment.share`. Its
delivery, after the Undo window, posts the shared comment (the body as sent) with the email, so
nothing reaches the client while it can be undone; Undo also undoes the send-backs.
"""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Final
from uuid import UUID, uuid5

from abacus.kernel import clock
from abacus.kernel.crypto import open_sealed, seal
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import (
    MissingAuditEvent,
    OutboxEvent,
    Ref,
    Scope,
    Target,
    UnitOfWork,
    audit_of_targets,
    event_sha256,
    uow,
)
from abacus.modules.agents.events import FollowUpSent
from abacus.modules.agents.follow_ups import MAX_SEQUENCE, today_in
from abacus.modules.agents.models import FollowUpSchedule
from abacus.modules.agents.repository import (
    follow_up_history,
    follow_up_item_rows,
    follow_up_return_rows,
    get_follow_up,
    insert_chase_draft,
    insert_follow_up_returns,
    insert_return_draft,
    set_follow_up,
    waiting_pairs,
)
from abacus.modules.communications.api import (
    REMINDER_TEMPLATE,
    RETURN_TEMPLATE,
    check_scope,
    compose_follow_up,
    deliver_follow_up,
)
from abacus.modules.engagements.api import EngagementRef, contact_portal_user, get_ref, lock_ref
from abacus.modules.evidence.api import return_files, undo_returned_files
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    Resource,
    allowed_actions,
    authorise,
    client_admins,
    firm_time_zone,
    issue_grant,
    names_of,
    void_grant,
)
from abacus.modules.requests.api import (
    FollowUpCandidate,
    check_return_comment,
    follow_up_candidates,
    insert_return_comment,
    live_files,
    selection_engagements,
)

UNDO_WINDOW: Final = timedelta(seconds=10)
GRANT_LIFETIME: Final = timedelta(days=7)
MAX_BODY: Final = 10_000
_ACTIONS: Final = ("follow_up.draft", "follow_up.send")
_LINK: Final = re.compile(r"https?://\S+")
RETURN: Final = "screening_return"
# A screening return's shared comment is one per follow-up: its id is derived from the
# follow-up's, so a redelivery posts nothing twice.
_RETURN_COMMENT: Final = UUID("5c2b1d3e-9f40-4a7e-8d61-0b9e2f6a1c47")


class FollowUpAlreadySent(DomainConflict):
    """The follow-up was sent: it can no longer be edited, sent again or dismissed."""

    code = "follow_up_already_sent"


class FollowUpNotWaiting(DomainConflict):
    """The follow-up was dismissed: nothing is waiting to be sent."""

    code = "follow_up_not_waiting"


class FollowUpOutOfScope(DomainConflict):
    """The body names something outside the engagement's scope; nothing was sent."""

    code = "out_of_scope"


class FollowUpUndoClosed(DomainConflict):
    """Undo is possible for 10 seconds after a send, by the person who sent it."""

    code = "undo_window_closed"


class FollowUpV2Only(DomainConflict):
    """This follow-up was drafted from a binder: send it from the binder's follow-up sheet."""

    code = "follow_up_v2_only"


class FollowUpSendAlone(DomainConflict):
    """A screening return sends back files: send it on its own, from its sheet."""

    code = "follow_up_send_alone"


class FollowUpEffectStarted(DomainConflict):
    """The email's delivery has started (its grant was consumed): it can no longer be undone."""

    code = "effect_started"


@dataclass(frozen=True)
class FollowUpItemView:
    request_item_id: UUID
    title: str
    due_on: date | None
    overdue: bool  # past its due date on the firm's business date


@dataclass(frozen=True)
class FollowUpReturnView:
    evidence_version_id: UUID
    reason_code: str


@dataclass(frozen=True)
class FollowUpView:
    id: UUID
    engagement_id: UUID
    binder_id: UUID | None
    kind: str
    status: str
    recipient_user_id: UUID
    recipient_contact_id: UUID | None
    recipient_name: str
    items: list[FollowUpItemView]
    subject: str
    body: str
    edited: bool
    drafted_by_kind: str
    template_key: str
    created_at: datetime
    sent_by: UUID | None
    sent_at: datetime | None
    undo_until: datetime | None
    allowed_actions: list[str]
    returning: list[FollowUpReturnView]  # a screening return's files, as drafted


def _human(ctx: AuthContext, action: str) -> None:
    """INV-1: a person's own act, never an agent, the platform or a support session."""
    if ctx.tenant.actor_kind != "human" or ctx.is_support:
        raise Forbidden(action, "role")


def fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _seal_context(follow_up_id: UUID) -> str:
    """What a sealed body is bound to (its follow-up), so it never opens as another's."""
    return fingerprint(f"follow_up.body:{follow_up_id}")


def _scope(row: FollowUpSchedule) -> Scope:
    return Scope(engagement_id=row.engagement_id)


def _target(follow_up_id: UUID) -> Target:
    return Target("follow_up", follow_up_id)


def _system(tenant_id: UUID) -> TenantContext:
    return TenantContext(tenant_id, "system", "agents.follow_ups")


# --- composition ---------------------------------------------------------------------------------


def group_by_contact(
    candidates: Sequence[FollowUpCandidate],
    recipients: Mapping[UUID, Sequence[tuple[UUID, UUID | None]]],
    waiting: set[tuple[UUID, UUID]],
) -> dict[tuple[UUID, UUID], list[tuple[FollowUpCandidate, UUID | None]]]:
    """(engagement, recipient) -> the requests to list, each once, in the candidates' order. A
    request already waiting in a draft to that recipient is left out. `recipients` maps a
    request to its (portal user, contact) pairs."""
    groups: dict[tuple[UUID, UUID], list[tuple[FollowUpCandidate, UUID | None]]] = defaultdict(
        list
    )
    seen: set[tuple[UUID, UUID]] = set()
    for item in candidates:
        for user, contact in recipients.get(item.id, []):
            if (user, item.id) in waiting or (user, item.id) in seen:
                continue
            seen.add((user, item.id))
            groups[(item.engagement_id, user)].append((item, contact))
    return dict(groups)


async def _recipients(
    ctx: AuthContext, candidates: Sequence[FollowUpCandidate]
) -> dict[UUID, list[tuple[UUID, UUID | None]]]:
    """Who is followed up about each request: its client assignee, else the binder's recipients
    who sign in to the portal, else the engagement's client admins (SPEC-027 P-4)."""
    found: dict[UUID, list[tuple[UUID, UUID | None]]] = {}
    admins: dict[UUID, list[UUID]] = {}
    portal: dict[tuple[UUID, UUID], UUID | None] = {}
    for item in candidates:
        if item.client_assignee_user_id is not None:
            found[item.id] = [(item.client_assignee_user_id, None)]
            continue
        pairs: list[tuple[UUID, UUID | None]] = []
        for contact in item.binder_recipient_contact_ids:
            key = (item.engagement_id, contact)
            if key not in portal:
                portal[key] = await contact_portal_user(ctx.tenant, item.engagement_id, contact)
            user = portal[key]
            if user is not None:
                pairs.append((user, contact))
        if not pairs:
            if item.engagement_id not in admins:
                admins[item.engagement_id] = await client_admins(ctx.tenant, item.engagement_id)
            pairs = [(user, None) for user in admins[item.engagement_id]]
        found[item.id] = pairs
    return found


async def _open_items(ctx: AuthContext, row: FollowUpSchedule) -> list[tuple[UUID, str]]:
    return [(c.id, c.title) for c in await _open_candidates(ctx, row)]


async def _open_candidates(ctx: AuthContext, row: FollowUpSchedule) -> list[FollowUpCandidate]:
    """The follow-up's requests still open for the client, as the caller may read them."""
    async with tenant_session(ctx.tenant) as session:
        ids = [i.request_item_id for i in await follow_up_item_rows(session, row.id)]
    # In the requests' own order (due date, then when they were made), as they were drafted.
    return await follow_up_candidates(ctx, [], ids, returning=row.kind == RETURN)


async def _content(
    tenant_id: UUID, row: FollowUpSchedule, items: Sequence[tuple[UUID, str]]
) -> tuple[str, str]:
    """The subject from the template; the body the person edited or sent, else composed now."""
    key = row.template_key or REMINDER_TEMPLATE
    titles = [t for _, t in items] or ["-"]
    composed = await compose_follow_up(
        tenant_id, row.engagement_id, row.recipient_user_id, titles, key
    )
    if row.body_sealed is not None:
        body = (await open_sealed(tenant_id, row.body_sealed, _seal_context(row.id))).decode()
        return composed.subject, body
    return composed.subject, composed.body


async def _view(ctx: AuthContext, row: FollowUpSchedule) -> FollowUpView:
    ref = await get_ref(ctx, row.engagement_id)
    resource = ref.resource()
    open_ = await _open_candidates(ctx, row)
    items = [(c.id, c.title) for c in open_]
    subject, body = await _content(ctx.tenant_id, row, items)
    now = await clock.now(ctx.tenant)
    today = today_in(await firm_time_zone(ctx.tenant), now)
    undo_until = (
        row.not_before
        if row.status == "sent" and row.not_before is not None and now < row.not_before
        else None
    )
    names = await names_of([row.recipient_user_id])
    returning: list[FollowUpReturnView] = []
    if row.kind == RETURN:
        async with tenant_session(ctx.tenant) as session:
            returning = [
                FollowUpReturnView(r.evidence_version_id, r.reason_code)
                for r in await follow_up_return_rows(session, row.id)
            ]
    return FollowUpView(
        id=row.id,
        engagement_id=row.engagement_id,
        binder_id=row.binder_id,
        kind=row.kind,
        status=row.status,
        recipient_user_id=row.recipient_user_id,
        recipient_contact_id=row.recipient_contact_id,
        recipient_name=names.get(row.recipient_user_id, ""),
        items=[
            FollowUpItemView(c.id, c.title, c.due_on, c.due_on is not None and c.due_on < today)
            for c in open_
        ],
        subject=subject,
        body=body,
        edited=row.edit_fingerprint is not None,
        drafted_by_kind=row.drafted_by_kind,
        template_key=row.template_key or REMINDER_TEMPLATE,
        created_at=row.created_at,
        sent_by=row.sent_by,
        sent_at=row.sent_at,
        undo_until=undo_until,
        allowed_actions=_state_actions(
            row, set(await allowed_actions(ctx, resource, _ACTIONS)), ctx.user_id, undo_until
        ),
        returning=returning,
    )


def _state_actions(
    row: FollowUpSchedule, allowed: set[str], user_id: UUID, undo_until: datetime | None
) -> list[str]:
    """What the caller may do now: edit, send and dismiss a waiting draft; only its sender may
    Undo a sent one, inside the window; nothing on a dismissed or delivered one."""
    if row.status == "drafted":
        return sorted(allowed)
    if row.status == "sent" and undo_until is not None and row.sent_by == user_id:
        return sorted(allowed & {"follow_up.send"})
    return []


# --- draft ---------------------------------------------------------------------------------------


async def draft_for(
    ctx: AuthContext, binder_ids: Sequence[UUID], item_ids: Sequence[UUID]
) -> list[FollowUpView]:
    """BND-01 b / BND-02 d: one draft per client contact per engagement over the selection.
    Nothing to chase (or everything already waiting) drafts nothing. Before anything is written:
    409 `binder_not_published` for a binder that isn't Published, 409 `out_of_scope` when a
    request title names something outside its engagement, 409 `follow_up_template_missing` when
    no Reminder template is published. Concurrent requests never duplicate a draft: the waiting
    drafts are read inside the unit of work and one open draft per contact is a unique index
    (a second request's requests join the first's draft unless it was edited)."""
    _human(ctx, "follow_up.draft")
    # ED-082 (Q-03-T038): authorise on every engagement the selection names, before reading
    # what is open, so a selection with nothing to chase answers 201 with no drafts (or 404 for
    # a binder the caller may not read) instead of an unchecked route.
    named = await selection_engagements(ctx, binder_ids, item_ids)
    refs: dict[UUID, EngagementRef] = {}
    for engagement_id in sorted(named, key=str):
        refs[engagement_id] = await get_ref(ctx, engagement_id)
        await authorise(ctx, "follow_up.draft", refs[engagement_id].resource())
    candidates = await follow_up_candidates(ctx, binder_ids, item_ids)
    for engagement_id in sorted({c.engagement_id for c in candidates} - set(refs), key=str):
        refs[engagement_id] = await get_ref(ctx, engagement_id)
        await authorise(ctx, "follow_up.draft", refs[engagement_id].resource())
    for item in candidates:
        if await _out_of_scope(ctx, refs[item.engagement_id], item.title):
            raise FollowUpOutOfScope(facts={"request_item_id": str(item.id)})
    recipients = await _recipients(ctx, candidates)
    every = sorted({u for pairs in recipients.values() for u, _ in pairs}, key=str)
    today = today_in(await firm_time_zone(ctx.tenant), await clock.now(ctx.tenant))
    made: list[UUID] = []
    try:
        async with uow(ctx.tenant) as tx:
            waiting = await waiting_pairs(tx.session, every)
            history = await follow_up_history(tx.session, [c.id for c in candidates])
            for (engagement_id, user), entries in group_by_contact(
                candidates, recipients, waiting
            ).items():
                rows: list[tuple[FollowUpCandidate, int]] = []
                for item, _contact in entries:
                    due = item.due_on or today
                    sent = sum(1 for i, d, _n, _at in history if i == item.id and d == due)
                    if sent < MAX_SEQUENCE:
                        rows.append((item, sent + 1))
                if not rows:
                    continue
                contacts = {c for _, c in entries if c is not None}
                binders = {i.binder_id for i, _ in rows}
                composed = await compose_follow_up(
                    ctx.tenant_id, engagement_id, user, [i.title for i, _ in rows]
                )
                body_fp = fingerprint(composed.body)
                drafted = await insert_chase_draft(
                    tx.session,
                    tenant_id=ctx.tenant_id,
                    engagement_id=engagement_id,
                    recipient_user_id=user,
                    items=[(i.id, i.due_on or today, n) for i, n in rows],
                    binder_id=next(iter(binders)) if len(binders) == 1 else None,
                    recipient_contact_id=next(iter(contacts)) if len(contacts) == 1 else None,
                    template_key=REMINDER_TEMPLATE,
                    body_fingerprint=body_fp,
                )
                if drafted is None or drafted[1] == 0:
                    continue  # an edited draft waits for this contact, or nothing was new
                follow_up_id, added = drafted
                tx.record(
                    "follow_up.drafted",
                    target=_target(follow_up_id),
                    after=Ref(items=added, body=body_fp),
                    scope=Scope(engagement_id=engagement_id),
                )
                made.append(follow_up_id)
    except MissingAuditEvent:  # nothing was drafted, so nothing is recorded
        return []
    return [await read(ctx, f) for f in dict.fromkeys(made)]


async def draft_return(
    ctx: AuthContext,
    engagement_id: UUID,
    item_id: UUID,
    returning: Sequence[UUID],
    reason_code: str,
) -> FollowUpView:
    """SHL-20 b: "Draft follow-up" on a flagged card. One draft for the request, composed from
    the firm's published Return template, to its first recipient (DEC-220's order), naming the
    files it returns with the reason. The request must be the client's to answer again: client
    visible, Uploaded or Returned, in a Published binder; each file a live fulfilment of it (else
    404). Before anything is written: 409 `out_of_scope` when the request's title names
    something outside the engagement, 409 `follow_up_template_missing` when no Return template
    is published. Drafting decides nothing: the send returns the files (`_send_one`)."""
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "follow_up.draft", ref.resource())
    found = [
        c
        for c in await follow_up_candidates(ctx, [], [item_id], returning=True)
        if c.engagement_id == engagement_id
    ]
    if not found:
        raise NotFound("request_item")
    [item] = found
    files = list(dict.fromkeys(returning))
    live = set(await live_files(ctx, item.id))
    if not files or any(f not in live for f in files):
        raise NotFound("evidence_version")
    if await _out_of_scope(ctx, ref, item.title):
        raise FollowUpOutOfScope(facts={"request_item_id": str(item.id)})
    pairs = (await _recipients(ctx, [item])).get(item.id, [])
    if not pairs:
        raise NotFound("recipient")
    user, contact = pairs[0]
    composed = await compose_follow_up(
        ctx.tenant_id, engagement_id, user, [item.title], RETURN_TEMPLATE
    )
    body_fp = fingerprint(composed.body)
    today = today_in(await firm_time_zone(ctx.tenant), await clock.now(ctx.tenant))
    async with uow(ctx.tenant) as tx:
        follow_up_id = await insert_return_draft(
            tx.session,
            tenant_id=ctx.tenant_id,
            engagement_id=engagement_id,
            binder_id=item.binder_id,
            recipient_user_id=user,
            request_item_id=item.id,
            due_on=item.due_on or today,
            template_key=RETURN_TEMPLATE,
            body_fingerprint=body_fp,
        )
        if contact is not None:
            await set_follow_up(tx.session, follow_up_id, {"recipient_contact_id": contact})
        await insert_follow_up_returns(
            tx.session, ctx.tenant_id, follow_up_id, [(f, reason_code) for f in files]
        )
        tx.record(
            "follow_up.drafted",
            target=_target(follow_up_id),
            after=Ref(items=1, files=len(files), body=body_fp),
            scope=Scope(engagement_id=engagement_id),
        )
    return await read(ctx, follow_up_id)


async def read(ctx: AuthContext, follow_up_id: UUID) -> FollowUpView:
    async with tenant_session(ctx.tenant) as session:
        row = await get_follow_up(session, follow_up_id)
    if row is None:
        raise NotFound("follow_up")
    ref = await get_ref(ctx, row.engagement_id)
    await authorise(ctx, "follow_up.draft", ref.resource())
    return await _view(ctx, row)


# --- edit, send, undo, dismiss -------------------------------------------------------------------


async def _locked(
    tx: UnitOfWork, ctx: AuthContext, follow_up_id: UUID, action: str
) -> tuple[FollowUpSchedule, EngagementRef, Resource]:
    row = await get_follow_up(tx.session, follow_up_id, lock=True)
    if row is None:
        raise NotFound("follow_up")
    ref = await lock_ref(tx, row.engagement_id)
    resource = ref.resource()
    await authorise(ctx, action, resource)
    return row, ref, resource


def _waiting(row: FollowUpSchedule) -> None:
    if row.status == "sent":
        raise FollowUpAlreadySent
    if row.status != "drafted":
        raise FollowUpNotWaiting


async def edit(ctx: AuthContext, follow_up_id: UUID, body: str) -> FollowUpView:
    """The person's own wording replaces the composed body (sealed; the edit's fingerprint is
    kept). Edit before sending only."""
    _human(ctx, "follow_up.draft")
    text = body.replace("\r\n", "\n").strip()
    if not text or len(text) > MAX_BODY:
        raise ValueError("a follow-up body is 1..10000 characters")
    async with uow(ctx.tenant) as tx:
        row, _ref, _resource = await _locked(tx, ctx, follow_up_id, "follow_up.draft")
        _waiting(row)
        sealed = await seal(ctx.tenant_id, text.encode(), _seal_context(row.id))
        edit_fp = fingerprint(text)
        await set_follow_up(
            tx.session, row.id, {"body_sealed": sealed, "edit_fingerprint": edit_fp}
        )
        tx.record(
            "follow_up.edited",
            target=_target(row.id),
            after=Ref(body=edit_fp),
            scope=_scope(row),
        )
    return await read(ctx, follow_up_id)


async def _send_one(
    tx: UnitOfWork, ctx: AuthContext, follow_up_id: UUID, *, alone: bool = True
) -> None:
    row, ref, resource = await _locked(tx, ctx, follow_up_id, "follow_up.send")
    _waiting(row)
    if row.kind == RETURN and not alone:  # its sender sees the files it returns (ADR-005)
        raise FollowUpSendAlone(facts={"follow_up_id": str(row.id)})
    now = await clock.now(ctx.tenant)
    items = await _open_items(ctx, row)
    if not items:  # everything it named was answered meanwhile: nothing to send
        await set_follow_up(
            tx.session,
            row.id,
            {"status": "dismissed", "decided_by": ctx.user_id, "decided_at": now},
        )
        tx.record("follow_up.dismissed", target=_target(row.id), scope=_scope(row))
        return
    _subject, body = await _content(ctx.tenant_id, row, items)
    added = await _added_text(ctx.tenant_id, row, items, body) if row.edit_fingerprint else ""
    if await _any_out_of_scope(ctx, ref, [*(t for _, t in items), added]):
        raise FollowUpOutOfScope
    if row.kind == RETURN:
        await _return(tx, ctx, row, [i for i, _ in items], body)
    await _hold(tx, ctx, row, resource, body, now)


async def _return(
    tx: UnitOfWork, ctx: AuthContext, row: FollowUpSchedule, item_ids: Sequence[UUID], body: str
) -> None:
    """A screening return's send, in the grant's unit of work: its sender may share the comment
    delivery will post (the body is a comment's), and each file is sent back with its reason
    (evidence's decision, the request `returned`)."""
    [item_id] = item_ids
    await check_return_comment(ctx, row.engagement_id, item_id, body)
    returns = await follow_up_return_rows(tx.session, row.id)
    await return_files(
        tx,
        ctx,
        row.engagement_id,
        item_id,
        [(r.evidence_version_id, r.reason_code) for r in returns],
    )


async def _hold(
    tx: UnitOfWork,
    ctx: AuthContext,
    row: FollowUpSchedule,
    resource: Resource,
    body: str,
    now: datetime,
) -> None:
    """The send: the body frozen as sent, the `follow_up.sent` event held by an approval grant
    until the 10-s Undo window ends (ADR-161), the person recorded as sender (INV-5)."""
    undo_until = now + UNDO_WINDOW
    event = FollowUpSent(follow_up_id=row.id, engagement_id=row.engagement_id, sent_by=ctx.user_id)
    grant = await issue_grant(
        tx,
        ctx,
        action="follow_up.send",
        resource=resource,
        subject=_target(row.id),
        payload_sha256=event_sha256(event),
        not_before=undo_until,
        expires_at=undo_until + GRANT_LIFETIME,
    )
    sealed = await seal(ctx.tenant_id, body.encode(), _seal_context(row.id))
    await set_follow_up(
        tx.session,
        row.id,
        {
            "status": "sent",
            "sent_by": ctx.user_id,
            "sent_at": now,
            "not_before": undo_until,
            "decided_by": ctx.user_id,
            "decided_at": now,
            "body_sealed": sealed,
        },
    )
    tx.emit(event, not_before=undo_until, grant_id=grant)
    tx.record(
        "follow_up.sent",
        target=_target(row.id),
        after=Ref(grant=grant, body=fingerprint(body)),
        scope=_scope(row),
    )


async def _added_text(
    tenant_id: UUID, row: FollowUpSchedule, items: Sequence[tuple[UUID, str]], body: str
) -> str:
    """What the person wrote: the edited body's lines that the composed one doesn't have, links
    left out. The template text and the portal link are platform text; the request titles are
    checked on their own (DEC-220)."""
    composed = await compose_follow_up(
        tenant_id,
        row.engagement_id,
        row.recipient_user_id,
        [t for _, t in items],
        row.template_key or REMINDER_TEMPLATE,
    )
    known = set(composed.body.splitlines())
    added = "\n".join(line for line in body.splitlines() if line not in known)
    return _LINK.sub("", added)


async def _out_of_scope(ctx: AuthContext, ref: EngagementRef, body: str) -> bool:
    """Fail closed: a checker failure blocks the send as a violation does (SPEC-006 AC-7)."""
    if not body.strip():
        return False
    try:
        return bool(await check_scope(ctx, ref, body))
    except Exception:  # fail closed on any checker failure
        return True


async def _any_out_of_scope(ctx: AuthContext, ref: EngagementRef, texts: Sequence[str]) -> bool:
    """Each value on its own, so a title or a note can't hide behind the platform's text."""
    for text_ in texts:
        if await _out_of_scope(ctx, ref, text_):
            return True
    return False


async def check_send(ctx: AuthContext, follow_up_ids: Sequence[UUID]) -> None:
    """Authorise `follow_up.send` on each follow-up (read-only), so a replayed send is checked
    like the first one (ED-023's shape): the stored answer reaches only who may send now."""
    _human(ctx, "follow_up.send")
    async with tenant_session(ctx.tenant) as session:
        rows = [await get_follow_up(session, f) for f in dict.fromkeys(follow_up_ids)]
    for row in rows:
        if row is None:
            raise NotFound("follow_up")
        ref = await get_ref(ctx, row.engagement_id)
        await authorise(ctx, "follow_up.send", ref.resource())


async def send(ctx: AuthContext, follow_up_id: UUID) -> FollowUpView:
    """Human only. The email leaves when the Undo window ends (the grant's delivery)."""
    _human(ctx, "follow_up.send")
    async with uow(ctx.tenant) as tx:
        await _send_one(tx, ctx, follow_up_id)
    return await read(ctx, follow_up_id)


async def send_many(ctx: AuthContext, follow_up_ids: Sequence[UUID]) -> list[FollowUpView]:
    """BND-01 b "Send n follow-ups": all in one unit of work, or none (a refusal names the
    first that failed by its error). A screening return is sent on its own (409
    `follow_up_send_alone`)."""
    _human(ctx, "follow_up.send")
    ids = list(dict.fromkeys(follow_up_ids))
    async with uow(ctx.tenant) as tx:
        for follow_up_id in ids:
            await _send_one(tx, ctx, follow_up_id, alone=False)
    return [await read(ctx, f) for f in ids]


async def undo(ctx: AuthContext, follow_up_id: UUID) -> FollowUpView:
    """Within 10 s of a send, by its sender: void the grant (no email leaves) and put the draft
    back. Later, 409 `undo_window_closed`; once delivery consumed the grant, `effect_started`."""
    _human(ctx, "follow_up.send")
    async with uow(ctx.tenant) as tx:
        row, _ref, _resource = await _locked(tx, ctx, follow_up_id, "follow_up.send")
        now = await clock.now(ctx.tenant)
        if (
            row.status != "sent"
            or row.sent_by != ctx.user_id
            or row.not_before is None
            or now >= row.not_before
        ):
            raise FollowUpUndoClosed
        grant = await _sent_grant(tx, row.id)
        if grant is None or not await void_grant(tx, grant):
            raise FollowUpEffectStarted
        if row.kind == RETURN:  # the files and the request go back too
            returns = await follow_up_return_rows(tx.session, row.id)
            await undo_returned_files(
                tx, ctx, row.engagement_id, [r.evidence_version_id for r in returns]
            )
        values: dict[str, object] = {
            "status": "drafted",
            "sent_by": None,
            "sent_at": None,
            "not_before": None,
            "decided_by": None,
            "decided_at": None,
            "undone_at": now,
        }
        if row.edit_fingerprint is None:
            values["body_sealed"] = None  # composed again from the template when next read
        await set_follow_up(tx.session, row.id, values)
        tx.record(
            "follow_up.undone", target=_target(row.id), after=Ref(grant=grant), scope=_scope(row)
        )
    return await read(ctx, follow_up_id)


async def _sent_grant(tx: UnitOfWork, follow_up_id: UUID) -> UUID | None:
    sent = await audit_of_targets(
        tx.session, [("follow_up", follow_up_id)], None, 1, action="follow_up.sent"
    )
    if not sent or not sent[0].after_ref:
        return None
    try:
        return UUID(str(sent[0].after_ref.get("grant")))
    except ValueError:
        return None


async def dismiss(ctx: AuthContext, follow_up_id: UUID) -> FollowUpView:
    _human(ctx, "follow_up.send")
    async with uow(ctx.tenant) as tx:
        row, _ref, _resource = await _locked(tx, ctx, follow_up_id, "follow_up.send")
        _waiting(row)
        now = await clock.now(ctx.tenant)
        await set_follow_up(
            tx.session,
            row.id,
            {"status": "dismissed", "decided_by": ctx.user_id, "decided_at": now},
        )
        tx.record("follow_up.dismissed", target=_target(row.id), scope=_scope(row))
    return await read(ctx, follow_up_id)


# --- the SPEC-027 engagement routes ----------------------------------------------------------


async def send_overdue(
    ctx: AuthContext,
    engagement_id: UUID,
    follow_up_id: UUID,
    items: Sequence[str],
    note: str | None,
    send: bool,
) -> str:
    """The legacy engagement route (TASK-104's `FollowUps.tsx`), through the same controls as v2:
    human only; the P-4 tick's `overdue` drafts only (409 `follow_up_v2_only` for a binder's
    draft); each request title and the person's note scope-checked on their own (409
    `out_of_scope`, nothing written); the email held by an approval grant for the 10-s Undo
    window and delivered by the outbox. `items` are the draft's requests still overdue; with
    none, the draft is dismissed. Returns `sent` or `dismissed`."""
    _human(ctx, "follow_up.send")
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        resource = ref.resource()
        await authorise(ctx, "follow_up.send", resource)
        row = await get_follow_up(tx.session, follow_up_id, lock=True)
        if row is None or row.engagement_id != engagement_id:
            raise NotFound("follow_up")
        if row.kind != "overdue":
            raise FollowUpV2Only
        if row.status != "drafted":
            raise FollowUpNotWaiting
        now = await clock.now(ctx.tenant)
        if not send or not items:
            await set_follow_up(
                tx.session,
                row.id,
                {"status": "dismissed", "decided_by": ctx.user_id, "decided_at": now},
            )
            tx.record("follow_up.dismissed", target=_target(row.id), scope=_scope(row))
            return "dismissed"
        if await _any_out_of_scope(ctx, ref, [*items, note or ""]):
            raise FollowUpOutOfScope
        _subject, body = await overdue_email(
            ctx.tenant_id, engagement_id, row.recipient_user_id, items, note
        )
        if note:
            await set_follow_up(tx.session, row.id, {"note": note})
        await _hold(tx, ctx, row, resource, body, now)
    return "sent"


async def overdue_email(
    tenant_id: UUID,
    engagement_id: UUID,
    recipient_user_id: UUID,
    items: Sequence[str],
    note: str | None,
) -> tuple[str, str]:
    """The SPEC-027 draft's email: the published Reminder template, with the person's optional
    note after it (the preview is the email)."""
    composed = await compose_follow_up(tenant_id, engagement_id, recipient_user_id, items)
    body = f"{composed.body.rstrip()}\n\n{note}\n" if note else composed.body
    return composed.subject, body


# --- delivery ------------------------------------------------------------------------------------


async def on_follow_up_sent(event: OutboxEvent) -> None:
    """The relay delivers `follow_up.sent` only once its grant is consumed after the Undo window
    (a voided grant delivers nothing): communications sends the frozen body, once."""
    follow_up_id = UUID(str(event.payload["follow_up_id"]))
    system = _system(event.tenant_id)
    async with tenant_session(system) as session:
        row = await get_follow_up(session, follow_up_id)
    if row is None or row.status != "sent" or row.sent_by is None or row.body_sealed is None:
        return
    body = (await open_sealed(event.tenant_id, row.body_sealed, _seal_context(row.id))).decode()
    if row.kind == RETURN:
        await _post_return_comment(system, row, row.sent_by, body)
    composed = await compose_follow_up(
        event.tenant_id,
        row.engagement_id,
        row.recipient_user_id,
        ["-"],  # only the subject is used: a request list never appears in a subject
        row.template_key or REMINDER_TEMPLATE,
    )
    await deliver_follow_up(
        event.tenant_id,
        row.id,
        row.engagement_id,
        row.recipient_user_id,
        row.sent_by,
        composed.subject,
        body,
    )


async def _post_return_comment(
    system: TenantContext, row: FollowUpSchedule, sent_by: UUID, body: str
) -> None:
    """A screening return's shared comment on its request: the body as sent, by its sender, once
    (before the email, so a failed comment is retried with it)."""
    async with tenant_session(system) as session:
        [item] = await follow_up_item_rows(session, row.id)
    comment_id = uuid5(_RETURN_COMMENT, str(row.id))
    # The platform posts it for its sender (ADR-018): audit rows carry who it acts for.
    for_sender = TenantContext(
        system.tenant_id, system.actor_kind, system.actor_id, on_behalf_of_user_id=sent_by
    )
    try:
        async with uow(for_sender) as tx:
            if not await insert_return_comment(
                tx,
                row.tenant_id,
                row.engagement_id,
                item.request_item_id,
                comment_id=comment_id,
                author_user_id=sent_by,
                body=body,
            ):
                return  # posted by an earlier delivery
            tx.record(
                "comment.posted",
                target=Target("comment", comment_id),
                after=Ref(
                    request_item_id=item.request_item_id,
                    shared=1,
                    follow_up_id=row.id,
                    sent_by=sent_by,
                    body=fingerprint(body),
                ),
                scope=_scope(row),
            )
    except MissingAuditEvent:  # nothing was written
        return
