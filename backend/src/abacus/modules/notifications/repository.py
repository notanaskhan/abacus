"""Notifications data access: the `notifications` table only (ADR-008, ADR-103)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Column,
    DateTime,
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
