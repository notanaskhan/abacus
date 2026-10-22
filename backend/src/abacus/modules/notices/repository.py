"""Notices data access (F-03-T22): the `notices` subtype rows."""

from __future__ import annotations

from collections.abc import Mapping

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_INSERT = text(
    "INSERT INTO notices (tenant_id, work_item_id, engagement_id, notice_code, received_on) "
    "VALUES (:tenant_id, :work_item_id, :engagement_id, :notice_code, :received_on)"
)


async def insert_notices(session: AsyncSession, values: Mapping[str, object]) -> None:
    await session.execute(_INSERT, dict(values))
