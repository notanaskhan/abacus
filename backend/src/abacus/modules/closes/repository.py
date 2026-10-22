"""Closes data access (F-03-T22): the `closes` subtype rows."""

from __future__ import annotations

from collections.abc import Mapping

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_INSERT = text(
    "INSERT INTO closes (tenant_id, work_item_id, engagement_id, period) "
    "VALUES (:tenant_id, :work_item_id, :engagement_id, :period)"
)


async def insert_closes(session: AsyncSession, values: Mapping[str, object]) -> None:
    await session.execute(_INSERT, dict(values))
