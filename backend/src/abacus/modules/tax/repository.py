"""Tax data access (F-03-T22): the `tax_returns` subtype rows."""

from __future__ import annotations

from collections.abc import Mapping

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_INSERT = text(
    "INSERT INTO tax_returns (tenant_id, work_item_id, engagement_id, client_entity_id, "
    "form, tax_year) "
    "VALUES (:tenant_id, :work_item_id, :engagement_id, :client_entity_id, :form, "
    ":tax_year)"
)


async def insert_tax_returns(session: AsyncSession, values: Mapping[str, object]) -> None:
    await session.execute(_INSERT, dict(values))
