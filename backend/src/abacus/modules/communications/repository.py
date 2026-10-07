"""Communications data access: messages only (ADR-008, ADR-103)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.modules.communications.models import Message


async def insert_message(
    session: AsyncSession,
    *,
    message_id: UUID,
    tenant_id: UUID,
    engagement_id: UUID,
    channel: str,
    recipient_ref: str,
    body: str,
    status: str,
    violations: list[dict[str, str]],
    created_by: UUID,
) -> None:
    await session.execute(
        insert(Message).values(
            id=message_id,
            tenant_id=tenant_id,
            engagement_id=engagement_id,
            channel=channel,
            recipient_ref=recipient_ref,
            body=body,
            status=status,
            violations=violations,
            created_by=created_by,
        )
    )
