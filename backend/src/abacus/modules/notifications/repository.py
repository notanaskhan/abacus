"""Notifications data access: `notifications`, `notification_preferences` and
`notification_deliveries` only (ADR-008, ADR-103)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    FetchedValue,
    MetaData,
    String,
    Table,
    func,
    or_,
    select,
    text,
    update,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.modules.identity.api import AuthContext, visible

notifications = Table(
    "notifications",
    MetaData(),
    Column("id", PgUUID(as_uuid=True), primary_key=True),
    Column("tenant_id", PgUUID(as_uuid=True)),
    Column("recipient_user_id", PgUUID(as_uuid=True)),
    Column("kind", String),
    Column("event_id", PgUUID(as_uuid=True)),
    Column("engagement_id", PgUUID(as_uuid=True)),
    Column("subject_type", String),
    Column("subject_id", PgUUID(as_uuid=True)),
    Column("created_at", DateTime(timezone=True)),
    Column("read_at", DateTime(timezone=True)),
    # P-01-T03 (C16)
    Column("category", String),
    Column("actor_user_id", PgUUID(as_uuid=True)),
    Column("actor_kind", String),
    Column("client_id", PgUUID(as_uuid=True)),
    Column("work_item_id", PgUUID(as_uuid=True)),
)


async def insert_notifications(session: AsyncSession, rows: list[dict[str, object]]) -> int:
    """Insert, ignoring rows already made for this event and recipient (at least once, AC-1)."""
    if not rows:
        return 0
    result = await session.execute(
        pg_insert(notifications)
        .values(rows)
        .on_conflict_do_nothing(constraint="notifications_once")
        .returning(notifications.c.id)
    )
    return len(result.all())


async def list_own(
    session: AsyncSession,
    ctx: AuthContext,
    *,
    unread_only: bool,
    before: datetime | None,
    limit: int,
) -> Sequence[Row[tuple[object, ...]]]:
    query = select(notifications).where(
        notifications.c.recipient_user_id == ctx.user_id,
        or_(
            notifications.c.engagement_id.is_(None),
            visible(ctx, "engagement.read_metadata", notifications.c.engagement_id),
        ),
    )
    if unread_only:
        query = query.where(notifications.c.read_at.is_(None))
    if before is not None:
        query = query.where(notifications.c.created_at < before)
    query = query.order_by(notifications.c.created_at.desc(), notifications.c.id).limit(limit)
    return (await session.execute(query)).all()


async def list_window(
    session: AsyncSession, ctx: AuthContext, *, since: datetime, cap: int
) -> Sequence[Row[tuple[object, ...]]]:
    """P-01-T06: the caller's own since `since`, newest first, at most `cap` (walls apply)."""
    query = (
        select(notifications)
        .where(
            notifications.c.recipient_user_id == ctx.user_id,
            notifications.c.created_at >= since,
            or_(
                notifications.c.engagement_id.is_(None),
                visible(ctx, "engagement.read_metadata", notifications.c.engagement_id),
            ),
        )
        .order_by(notifications.c.created_at.desc(), notifications.c.id)
        .limit(cap)
    )
    return (await session.execute(query)).all()


async def unread_count(session: AsyncSession, ctx: AuthContext) -> int:
    count = await session.scalar(
        select(func.count())
        .select_from(notifications)
        .where(
            notifications.c.recipient_user_id == ctx.user_id,
            notifications.c.read_at.is_(None),
            or_(
                notifications.c.engagement_id.is_(None),
                visible(ctx, "engagement.read_metadata", notifications.c.engagement_id),
            ),
        )
    )
    return count or 0


async def mark_read(session: AsyncSession, ctx: AuthContext, notification_id: UUID) -> bool:
    """True when the caller owns it (and may still see it); sets `read_at` once (AC-6)."""
    owned = await session.scalar(
        select(notifications.c.id).where(
            notifications.c.id == notification_id,
            notifications.c.recipient_user_id == ctx.user_id,
            or_(
                notifications.c.engagement_id.is_(None),
                visible(ctx, "engagement.read_metadata", notifications.c.engagement_id),
            ),
        )
    )
    if owned is None:
        return False
    await session.execute(
        update(notifications)
        .where(notifications.c.id == notification_id, notifications.c.read_at.is_(None))
        .values(read_at=func.clock_timestamp())
    )
    return True


async def mark_all_read(session: AsyncSession, ctx: AuthContext) -> int:
    result = await session.execute(
        update(notifications)
        .where(
            notifications.c.recipient_user_id == ctx.user_id,
            notifications.c.read_at.is_(None),
            or_(
                notifications.c.engagement_id.is_(None),
                visible(ctx, "engagement.read_metadata", notifications.c.engagement_id),
            ),
        )
        .values(read_at=func.clock_timestamp())
        .returning(notifications.c.id)
    )
    return len(result.all())


async def purge(session: AsyncSession, days: int) -> int:
    count = await session.scalar(text("SELECT notifications_purge(:days)"), {"days": days})
    return int(count or 0)


# --- P-01-T12: per-kind preferences and the email channel's delivery rows (C16) ----------------

preferences = Table(
    "notification_preferences",
    MetaData(),
    Column("tenant_id", PgUUID(as_uuid=True), primary_key=True),
    Column("user_id", PgUUID(as_uuid=True), primary_key=True),
    Column("kind", String, primary_key=True),
    Column("in_app", Boolean),
    Column("email", Boolean),
    Column("updated_at", DateTime(timezone=True)),
)
deliveries = Table(
    "notification_deliveries",
    MetaData(),
    Column("id", PgUUID(as_uuid=True), primary_key=True, server_default=FetchedValue()),
    Column("tenant_id", PgUUID(as_uuid=True)),
    Column("notification_id", PgUUID(as_uuid=True)),
    Column("channel", String),
    Column("status", String),
    Column("message_ref", String),
    Column("created_at", DateTime(timezone=True)),
)


async def own_preferences(session: AsyncSession, user_id: UUID) -> dict[str, tuple[bool, bool]]:
    """The person's stored choices, kind to (in app, email); a kind not stored has none."""
    rows = await session.execute(
        select(preferences.c.kind, preferences.c.in_app, preferences.c.email).where(
            preferences.c.user_id == user_id
        )
    )
    return {str(kind): (bool(in_app), bool(email)) for kind, in_app, email in rows}


async def email_choices(
    session: AsyncSession, kind: str, user_ids: list[UUID]
) -> dict[UUID, bool]:
    """Stored email choices for one kind, by person (the platform at fan-out)."""
    if not user_ids:
        return {}
    rows = await session.execute(
        select(preferences.c.user_id, preferences.c.email).where(
            preferences.c.kind == kind, preferences.c.user_id.in_(user_ids)
        )
    )
    return {user: bool(email) for user, email in rows}


async def save_preference(
    session: AsyncSession, tenant_id: UUID, user_id: UUID, kind: str, in_app: bool, email: bool
) -> bool:
    """Insert or change one choice; True when something changed."""
    stored = await session.execute(
        pg_insert(preferences)
        .values(tenant_id=tenant_id, user_id=user_id, kind=kind, in_app=in_app, email=email)
        .on_conflict_do_update(
            index_elements=[preferences.c.tenant_id, preferences.c.user_id, preferences.c.kind],
            set_={"in_app": in_app, "email": email, "updated_at": func.abacus_now()},
            where=(preferences.c.in_app != in_app) | (preferences.c.email != email),
        )
        .returning(preferences.c.kind)
    )
    return stored.first() is not None


async def made_for_event(
    session: AsyncSession, event_id: UUID, kind: str
) -> dict[UUID, tuple[UUID, UUID | None]]:
    """The event's notifications of one kind: id to (recipient, engagement). For the platform's
    fan-out of the same event, never returned to a caller."""
    rows = await session.execute(
        select(
            notifications.c.id,
            notifications.c.recipient_user_id,
            notifications.c.engagement_id,
        ).where(notifications.c.event_id == event_id, notifications.c.kind == kind)
    )
    return {nid: (user, engagement) for nid, user, engagement in rows}


async def insert_delivery(
    session: AsyncSession, tenant_id: UUID, notification_id: UUID, status: str
) -> bool:
    """One email delivery row per notification (the UNIQUE makes a redelivery a no-op)."""
    made = await session.execute(
        pg_insert(deliveries)
        .values(
            tenant_id=tenant_id, notification_id=notification_id, channel="email", status=status
        )
        .on_conflict_do_nothing(constraint="notification_deliveries_once")
        .returning(deliveries.c.id)
    )
    return made.first() is not None


async def queued_for_event(session: AsyncSession, event_id: UUID) -> list[UUID]:
    """The event's notifications whose email is still queued: the ones to start."""
    rows = await session.execute(
        select(deliveries.c.notification_id)
        .join(notifications, notifications.c.id == deliveries.c.notification_id)
        .where(
            notifications.c.event_id == event_id,
            deliveries.c.channel == "email",
            deliveries.c.status == "queued",
        )
    )
    return [nid for (nid,) in rows]


@dataclass(frozen=True)
class DeliveryFacts:
    status: str
    kind: str
    recipient_user_id: UUID
    engagement_id: UUID | None


async def delivery_facts(session: AsyncSession, notification_id: UUID) -> DeliveryFacts | None:
    """What the email activity proves itself from: the delivery row and its notification."""
    row = (
        await session.execute(
            select(
                deliveries.c.status,
                notifications.c.kind,
                notifications.c.recipient_user_id,
                notifications.c.engagement_id,
            )
            .join(notifications, notifications.c.id == deliveries.c.notification_id)
            .where(
                deliveries.c.notification_id == notification_id, deliveries.c.channel == "email"
            )
        )
    ).first()
    if row is None:
        return None
    return DeliveryFacts(str(row.status), str(row.kind), row.recipient_user_id, row.engagement_id)


async def settle_delivery(
    session: AsyncSession, notification_id: UUID, status: str, message_ref: str | None
) -> bool:
    """A queued email's outcome, once: True when this call moved it."""
    moved = await session.execute(
        update(deliveries)
        .where(
            deliveries.c.notification_id == notification_id,
            deliveries.c.channel == "email",
            deliveries.c.status == "queued",
        )
        .values(status=status, message_ref=message_ref)
        .returning(deliveries.c.id)
    )
    return moved.first() is not None
