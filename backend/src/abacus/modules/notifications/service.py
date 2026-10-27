"""Notifications (SPEC-013): catalogued events become per-recipient notifications; each person
reads and marks only their own, and walls apply at read time."""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final
from uuid import UUID, uuid4

from abacus.kernel.clock import now
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainInvalid, NotFound
from abacus.kernel.listing import Position, decode_cursor, encode_cursor, query_hash
from abacus.kernel.logging import get_logger
from abacus.kernel.metrics import meter
from abacus.kernel.uow import MissingAuditEvent, OutboxEvent, Ref, Target, uow
from abacus.modules.identity.api import (
    AuthContext,
    engagement_resource,
    hidden_clients,
    member_facts,
)
from abacus.modules.notifications.catalogue import CATALOGUE
from abacus.modules.notifications.email import queue_emails, start_queued
from abacus.modules.notifications.kinds import (
    AGENT_KINDS,
    Fact,
    InlineAction,
    Row,
    kind_of,
    registered,
)
from abacus.modules.notifications.repository import (
    insert_notifications,
    list_own,
    list_window,
    mark_all_read,
    mark_read,
    own_preferences,
    purge,
    save_preference,
    unread_count,
)

RETENTION_DAYS: Final = 180
PURGE_INTERVAL_SECONDS: Final = 24 * 3600
MAX_PAGE: Final = 100
_log = get_logger(__name__)
_created = meter(__name__).create_counter(
    "abacus.notifications.created", description="Notifications created, by kind"
)
_dropped = meter(__name__).create_counter(
    "abacus.notifications.dropped", description="Events of an unregistered kind, by kind"
)


@dataclass(frozen=True)
class NotificationView:
    id: UUID
    kind: str
    engagement_id: UUID | None
    subject_type: str
    subject_id: UUID
    created_at: datetime
    read: bool


@dataclass(frozen=True)
class NotificationPage:
    items: list[NotificationView]
    unread_count: int


def _uuid(value: object) -> UUID | None:
    return UUID(str(value)) if value is not None else None


async def _reauthorised(
    ctx: TenantContext, engagement_id: UUID | None, recipients: list[UUID]
) -> list[UUID]:
    """INV-3 at fan-out (P-01-T06): only active members of the firm (SPEC-013 AC-2), and nobody
    walled from the engagement's client, get a row. Read time checks again, so a wall added
    later hides rows already made. P-01-T14: a payload naming a revoked member or someone of
    another firm no longer makes their row (or, for the latter, fails the whole event)."""
    recipients = [user for user in recipients if await member_facts(ctx, user) is not None]
    if engagement_id is None or not recipients:
        return recipients
    try:
        client = (await engagement_resource(ctx, engagement_id)).client_id
    except NotFound:
        return []
    if client is None:
        return recipients
    return [user for user in recipients if not await hidden_clients(ctx, user, [client])]


async def notify(event: OutboxEvent) -> None:
    """The relay's handler for every catalogued event (AC-1 to AC-3). Idempotent."""
    entry = CATALOGUE.get(event.event_type)
    if entry is None:
        return
    kind = kind_of(entry.kind)
    if kind is None:  # C16: fail closed, counted
        _dropped.add(1, {"kind": entry.kind})
        return
    payload = event.payload
    ctx = TenantContext(event.tenant_id, "system", "notifications")
    engagement = _uuid(payload.get(entry.engagement_key)) if entry.engagement_key else None
    recipients = await _reauthorised(
        ctx, engagement, await entry.recipients(event.tenant_id, payload)
    )
    named = _uuid(payload.get(entry.subject_key)) if entry.subject_key else None
    subject, subject_type = (named, entry.subject_type) if named else (event.tenant_id, "firm")
    actor = _uuid(payload.get("by_user") or payload.get("actor_user_id"))
    rows: list[dict[str, object]] = [
        {
            "id": uuid4(),
            "tenant_id": event.tenant_id,
            "recipient_user_id": user,
            "kind": entry.kind,
            "event_id": event.event_id,
            "engagement_id": engagement,
            "subject_type": subject_type,
            "subject_id": subject,
            "category": kind.category,
            "actor_user_id": actor,
            # INV-5 (P-01-T14): an agent-originated kind's row reads as the agent's, unless the
            # event names the person who acted (P-04-T26, DEC-605: a person routed a proposal).
            "actor_kind": (
                "human"
                if actor is not None
                else "agent"
                if entry.kind in AGENT_KINDS
                else "system"
            ),
            "client_id": _uuid(payload.get("client_id")),
            "work_item_id": _uuid(payload.get("work_item_id")),
        }
        for user in recipients
    ]
    if not rows:
        return
    made = 0
    try:
        async with uow(ctx) as tx:
            made = await insert_notifications(tx.session, rows)
            if made:
                tx.record(
                    "notification.created",
                    target=Target("event", event.event_id),
                    after=Ref(count=made),
                )
    except MissingAuditEvent:
        pass  # a redelivery: every row already existed; their emails are still checked
    if made:
        _created.add(made, {"kind": entry.kind})
    # P-01-T12: the email channel. Delivery rows once, then each queued email starts once.
    await queue_emails(ctx, event.event_id, entry.kind)
    await start_queued(ctx, event.event_id)


async def my_notifications(
    ctx: AuthContext, *, unread_only: bool, before: datetime | None, limit: int
) -> NotificationPage:
    """The caller's own, newest first, with the unread count (AC-4, AC-5)."""
    limit = max(1, min(limit, MAX_PAGE))
    async with tenant_session(ctx.tenant) as session:
        rows = await list_own(session, ctx, unread_only=unread_only, before=before, limit=limit)
        count = await unread_count(session, ctx)
    return NotificationPage(
        [
            NotificationView(
                r.id,
                r.kind,
                r.engagement_id,
                r.subject_type,
                r.subject_id,
                r.created_at,
                r.read_at is not None,
            )
            for r in rows
        ],
        count,
    )


FEED_DAYS: Final = 30
WINDOW_CAP: Final = 500
Tab = str  # all | approvals | mentions | client_activity


@dataclass(frozen=True)
class FeedItem:
    id: UUID
    kind: str
    category: str
    created_at: datetime
    read: bool
    actor_kind: str
    actor_user_id: UUID | None
    subject_type: str
    subject_id: UUID
    engagement_id: UUID | None
    facts: dict[str, Fact]
    inline_actions: tuple[InlineAction, ...]
    pending: bool


@dataclass(frozen=True)
class Feed:
    items: list[FeedItem]
    next_cursor: str | None
    approvals: int
    mentions: int
    client_activity: int
    unread_count: int


def _in_tab(tab: Tab, category: str, pending: bool) -> bool:
    if tab == "approvals":
        return pending
    if tab == "mentions":
        return category == "mention"
    if tab == "client_activity":
        return category == "client_activity"
    return True


async def feed(
    ctx: AuthContext, *, tab: Tab, cursor: str | None, limit: int, days: int = FEED_DAYS
) -> Feed:
    """P-01-T06 (SHL-04): the caller's own in the last `days` (30 at most), on the P-36
    envelope. `pending` and `facts` resolve now through each kind's resolvers, so a decision
    taken elsewhere drops a row out of Approvals; walls apply at read time (INV-3)."""
    days = max(1, min(days, FEED_DAYS))
    since = await now(ctx.tenant) - timedelta(days=days)
    async with tenant_session(ctx.tenant) as session:
        window = await list_window(session, ctx, since=since, cap=WINDOW_CAP)
        chosen = await own_preferences(session, ctx.user_id)
    # P-01-T12: a kind the person turned off in the app is neither shown nor counted.
    window = [r for r in window if chosen.get(str(r.kind), (True, False))[0]]
    resolved: list[tuple[Row, object, bool]] = []
    for r in window:
        row = Row(r.id, r.kind, r.engagement_id, r.subject_type, r.subject_id, r.created_at)
        kind = kind_of(r.kind)
        pending = (
            await kind.pending(ctx.tenant, ctx.user_id, row)
            if kind is not None and kind.pending is not None
            else False
        )
        resolved.append((row, r, pending))
    category = {r.id: (r.category or "other") for r in window}
    unread = {r.id for r in window if r.read_at is None}
    listed = [t for t in resolved if _in_tab(tab, category[t[0].id], t[2])]
    resource = "notifications.feed"
    query = query_hash(tab=tab, days=days)
    if cursor is not None:
        at = decode_cursor(cursor, tenant_id=ctx.tenant_id, resource=resource, query=query)
        listed = [
            t
            for t in listed
            if (t[0].created_at.isoformat(), str(t[0].id)) < (str(at.key), at.id)
            or (t[0].created_at.isoformat() == at.key and str(t[0].id) > at.id)
        ]
    page, more = listed[:limit], len(listed) > limit
    items: list[FeedItem] = []
    for row, r, pending in page:
        kind = kind_of(row.kind)
        facts = await kind.facts(ctx.tenant, row) if kind is not None and kind.facts else {}
        items.append(
            FeedItem(
                id=row.id,
                kind=row.kind,
                category=category[row.id],
                created_at=row.created_at,
                read=row.id not in unread,
                actor_kind=str(getattr(r, "actor_kind", None) or "system"),
                actor_user_id=getattr(r, "actor_user_id", None),
                subject_type=row.subject_type,
                subject_id=row.subject_id,
                engagement_id=row.engagement_id,
                facts=facts,
                inline_actions=kind.inline_actions if kind is not None and pending else (),
                pending=pending,
            )
        )
    last = page[-1][0] if page and more else None
    next_cursor = (
        encode_cursor(
            Position(last.created_at.isoformat(), str(last.id)),
            tenant_id=ctx.tenant_id,
            resource=resource,
            query=query,
        )
        if last is not None
        else None
    )
    return Feed(
        items=items,
        next_cursor=next_cursor,
        approvals=sum(1 for _, _, pending in resolved if pending),
        mentions=sum(1 for r in window if r.category == "mention" and r.id in unread),
        client_activity=sum(
            1 for r in window if r.category == "client_activity" and r.id in unread
        ),
        unread_count=len(unread),
    )


async def read_one(ctx: AuthContext, notification_id: UUID) -> None:
    """AC-6: the caller's own only (404 otherwise). Audited like every state change (AGENTS.md
    #3; TASK-028 decision), though it is only the reader's own state."""
    async with uow(ctx.tenant) as tx:
        if not await mark_read(tx.session, ctx, notification_id):
            raise NotFound("notification")
        tx.record("notification.read", target=Target("notification", notification_id))


async def read_all(ctx: AuthContext) -> int:
    try:
        async with uow(ctx.tenant) as tx:
            count = await mark_all_read(tx.session, ctx)
            if count:
                tx.record(
                    "notification.read_all",
                    target=Target("user", ctx.user_id),
                    after=Ref(count=count),
                )
    except MissingAuditEvent:
        return 0  # nothing was unread
    return count


async def purge_once() -> int:
    """One purge pass (AC-10): notifications older than the retention, across firms, through the
    definer function, which returns a count. Audited as the system. `NotificationPurgeWorkflow`
    runs it daily on a Schedule (Q-01-T26)."""
    platform = TenantContext(UUID(int=0), "system", "notifications:purge")
    async with uow(platform) as tx:
        count = await purge(tx.session, RETENTION_DAYS)
        tx.record(
            "notifications.purged",
            target=Target("retention", RETENTION_DAYS),
            after=Ref(count=count),
        )
    _log.info("notifications.purged", count=count)
    return count


async def run_purge_job(stop: asyncio.Event) -> None:
    """Daily until `stop` (AC-10). The worker no longer runs it: the daily pass is a Schedule
    (Q-01-T26). Kept as the loop the SPEC-013 back-fill test drives."""
    while not stop.is_set():
        try:
            await purge_once()
        except Exception as exc:
            _log.warning("notifications.purge_failed", error=type(exc).__name__)
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), PURGE_INTERVAL_SECONDS)


# --- P-01-T12: the person's own per-kind preferences (C16; OWN) ---------------------------------


class UnknownNotificationKind(DomainInvalid):
    """A preference names a kind that is not registered, or names one twice."""

    code = "unknown_notification_kind"


@dataclass(frozen=True)
class Preference:
    kind: str
    in_app: bool
    email: bool


def _default(code: str) -> tuple[bool, bool]:
    kind = kind_of(code)
    return (True, kind.email_default if kind is not None else False)


async def my_preferences(ctx: AuthContext) -> list[Preference]:
    """Every registered kind with the caller's choice, else the kind's default (in the app on;
    email as the kind declares)."""
    async with tenant_session(ctx.tenant) as session:
        stored = await own_preferences(session, ctx.user_id)
    return [Preference(code, *stored.get(code, _default(code))) for code in registered()]


async def set_my_preferences(ctx: AuthContext, items: list[Preference]) -> list[Preference]:
    """The caller's own choices only (OWN). An unchanged choice writes nothing."""
    codes = [i.kind for i in items]
    unknown = {c for c in codes if kind_of(c) is None or codes.count(c) > 1}
    if unknown:
        raise UnknownNotificationKind(facts={"kind": sorted(unknown)[0], "count": len(unknown)})
    try:
        async with uow(ctx.tenant) as tx:
            changed = 0
            for item in items:
                changed += await save_preference(
                    tx.session, ctx.tenant_id, ctx.user_id, item.kind, item.in_app, item.email
                )
            if changed:
                tx.record(
                    "notification_preference.changed",
                    target=Target("user", ctx.user_id),
                    after=Ref(count=changed),
                )
    except MissingAuditEvent:
        pass  # nothing changed
    return await my_preferences(ctx)
