"""Follow-ups v2: drafted by the platform, sent by a person (P-06-T14; DEC-74, DEC-220). PROTECTED.

BND-01 b and BND-02 d: a person picks binders or requests and the platform drafts one follow-up
per client contact per engagement, from the firm's published Reminder template (C16, in the
database), listing each open client-visible request once and never one already waiting in a
draft to that contact. The composition is the Request Chaser's (`drafted_by_kind = 'agent'`,
the C-31 marker); the person who asked is the audit actor.

A person edits the body (sealed; `edit_fingerprint`), then sends: human only (agent: deny,
DEC-74; `follow_up.sent` is in the human-only register), scope-checked (409 `out_of_scope`,
nothing written), and held by an approval grant until the 10-s Undo window ends (ADR-161). The
body sent is frozen in `body_sealed`; the relay's delivery of `follow_up.sent` sends the email
through communications (COMM-001). Undo within the window voids the grant and puts the draft
back; dismiss closes it. No model text reaches a client (DEC-79, ADR-111).
"""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Final
from uuid import UUID

from abacus.kernel import clock
from abacus.kernel.crypto import open_sealed, seal
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import (
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
    get_follow_up,
    insert_follow_up,
    set_follow_up,
    waiting_pairs,
)
from abacus.modules.communications.api import (
    REMINDER_TEMPLATE,
    check_scope,
    compose_follow_up,
    deliver_follow_up,
)
from abacus.modules.engagements.api import EngagementRef, contact_portal_user, get_ref, lock_ref
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
from abacus.modules.requests.api import FollowUpCandidate, follow_up_candidates

UNDO_WINDOW: Final = timedelta(seconds=10)
GRANT_LIFETIME: Final = timedelta(days=7)
MAX_BODY: Final = 10_000
_ACTIONS: Final = ("follow_up.draft", "follow_up.send")
_LINK: Final = re.compile(r"https?://\S+")


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
    return await follow_up_candidates(ctx, [], ids)


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
        allowed_actions=sorted(await allowed_actions(ctx, resource, _ACTIONS)),
    )


# --- draft ---------------------------------------------------------------------------------------


async def draft_for(
    ctx: AuthContext, binder_ids: Sequence[UUID], item_ids: Sequence[UUID]
) -> list[FollowUpView]:
    """BND-01 b / BND-02 d: one draft per client contact per engagement over the selection.
    Nothing to chase (or everything already waiting) drafts nothing. 409
    `follow_up_template_missing` before anything is written when no template is published."""
    _human(ctx, "follow_up.draft")
    candidates = await follow_up_candidates(ctx, binder_ids, item_ids)
    for engagement_id in sorted({c.engagement_id for c in candidates}, key=str):
        ref = await get_ref(ctx, engagement_id)
        await authorise(ctx, "follow_up.draft", ref.resource())
    recipients = await _recipients(ctx, candidates)
    every = sorted({u for pairs in recipients.values() for u, _ in pairs}, key=str)
    async with tenant_session(ctx.tenant) as session:
        waiting = await waiting_pairs(session, every)
        history = await follow_up_history(session, [c.id for c in candidates])
    groups = group_by_contact(candidates, recipients, waiting)
    today = today_in(await firm_time_zone(ctx.tenant), await clock.now(ctx.tenant))
    planned: list[tuple[UUID, UUID, list[tuple[FollowUpCandidate, int]], UUID | None, str]] = []
    for (engagement_id, user), entries in groups.items():
        rows: list[tuple[FollowUpCandidate, int]] = []
        for item, _contact in entries:
            due = item.due_on or today
            sent = sum(1 for i, d, _n, _at in history if i == item.id and d == due)
            if sent < MAX_SEQUENCE:
                rows.append((item, sent + 1))
        if not rows:
            continue
        contacts = {c for _, c in entries if c is not None}
        composed = await compose_follow_up(
            ctx.tenant_id, engagement_id, user, [i.title for i, _ in rows], REMINDER_TEMPLATE
        )
        planned.append(
            (
                engagement_id,
                user,
                rows,
                next(iter(contacts)) if len(contacts) == 1 else None,
                fingerprint(composed.body),
            )
        )
    made: list[UUID] = []
    if not planned:
        return []
    async with uow(ctx.tenant) as tx:
        for engagement_id, user, rows, contact, body_fp in planned:
            binders = {i.binder_id for i, _ in rows}
            follow_up_id = await insert_follow_up(
                tx.session,
                tenant_id=ctx.tenant_id,
                engagement_id=engagement_id,
                recipient_user_id=user,
                status="drafted",
                agent_run_id=None,
                items=[(i.id, i.due_on or today, n) for i, n in rows],
                kind="chase",
                drafted_by_kind="agent",
                binder_id=next(iter(binders)) if len(binders) == 1 else None,
                recipient_contact_id=contact,
                template_key=REMINDER_TEMPLATE,
                body_fingerprint=body_fp,
            )
            tx.record(
                "follow_up.drafted",
                target=_target(follow_up_id),
                after=Ref(items=len(rows), body=body_fp),
                scope=Scope(engagement_id=engagement_id),
            )
            made.append(follow_up_id)
    return [await read(ctx, f) for f in made]


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


async def _send_one(tx: UnitOfWork, ctx: AuthContext, follow_up_id: UUID) -> None:
    row, ref, resource = await _locked(tx, ctx, follow_up_id, "follow_up.send")
    _waiting(row)
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
    if row.edit_fingerprint is not None and await _out_of_scope(
        ctx, ref, await _added_text(ctx.tenant_id, row, items, body)
    ):
        raise FollowUpOutOfScope
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
    sealed = row.body_sealed or await seal(ctx.tenant_id, body.encode(), _seal_context(row.id))
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
    left out. The template is platform text and each request's wording passed the scope check
    when it was sent, so an unedited follow-up has nothing new to check (DEC-220)."""
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


async def send(ctx: AuthContext, follow_up_id: UUID) -> FollowUpView:
    """Human only. The email leaves when the Undo window ends (the grant's delivery)."""
    _human(ctx, "follow_up.send")
    async with uow(ctx.tenant) as tx:
        await _send_one(tx, ctx, follow_up_id)
    return await read(ctx, follow_up_id)


async def send_many(ctx: AuthContext, follow_up_ids: Sequence[UUID]) -> list[FollowUpView]:
    """BND-01 b "Send n follow-ups": all in one unit of work, or none (a refusal names the
    first that failed by its error)."""
    _human(ctx, "follow_up.send")
    ids = list(dict.fromkeys(follow_up_ids))
    async with uow(ctx.tenant) as tx:
        for follow_up_id in ids:
            await _send_one(tx, ctx, follow_up_id)
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
