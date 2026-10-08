"""Notifications (SPEC-013): catalogued events become per-recipient notifications; each person
reads and marks only their own, and walls apply at read time."""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass
from datetime import datetime
from typing import Final
from uuid import UUID, uuid4

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.logging import get_logger
from abacus.kernel.metrics import meter
from abacus.kernel.uow import MissingAuditEvent, OutboxEvent, Ref, Target, uow
from abacus.modules.identity.api import AuthContext
from abacus.modules.notifications.catalogue import CATALOGUE
from abacus.modules.notifications.repository import (
    insert_notifications,
    list_own,
    mark_all_read,
    mark_read,
    purge,
    unread_count,
)

RETENTION_DAYS: Final = 180
PURGE_INTERVAL_SECONDS: Final = 24 * 3600
MAX_PAGE: Final = 100
_log = get_logger(__name__)
_created = meter(__name__).create_counter(
    "abacus.notifications.created", description="Notifications created, by kind"
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


async def notify(event: OutboxEvent) -> None:
    """The relay's handler for every catalogued event (AC-1 to AC-3). Idempotent."""
    entry = CATALOGUE.get(event.event_type)
    if entry is None:
        return
    payload = event.payload
    recipients = await entry.recipients(event.tenant_id, payload)
    named = _uuid(payload.get(entry.subject_key)) if entry.subject_key else None
    subject, subject_type = (named, entry.subject_type) if named else (event.tenant_id, "firm")
    engagement = _uuid(payload.get(entry.engagement_key)) if entry.engagement_key else None
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
        }
        for user in recipients
    ]
    if not rows:
        return
    ctx = TenantContext(event.tenant_id, "system", "notifications")
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
        return  # a redelivery: every row already existed
    _created.add(made, {"kind": entry.kind})


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


async def run_purge_job(stop: asyncio.Event) -> None:
    """Daily until `stop` (AC-10). The definer function reads across firms and returns a count."""
    platform = TenantContext(UUID(int=0), "system", "notifications:purge")
    while not stop.is_set():
        try:
            async with uow(platform) as tx:
                count = await purge(tx.session, RETENTION_DAYS)
                tx.record(
                    "notifications.purged",
                    target=Target("retention", RETENTION_DAYS),
                    after=Ref(count=count),
                )
            _log.info("notifications.purged", count=count)
        except Exception as exc:
            _log.warning("notifications.purge_failed", error=type(exc).__name__)
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), PURGE_INTERVAL_SECONDS)
