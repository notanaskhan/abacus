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


# T-02-T07 (0403): the status machine's reads and writes.
_STATUS = text(
    "SELECT status, row_version FROM tax_returns WHERE tenant_id = :tenant_id "
    "AND work_item_id = :work_item_id FOR UPDATE"
)
_MOVE = text(
    "UPDATE tax_returns SET status = :to_status, row_version = row_version + 1 "
    "WHERE tenant_id = :tenant_id AND work_item_id = :work_item_id AND row_version = :seen"
)
_EVENT = text(
    "INSERT INTO tax_return_status_events (tenant_id, work_item_id, from_status, to_status, "
    "event, actor_kind, actor_id, on_behalf_of, reason) VALUES (:tenant_id, :work_item_id, "
    ":from_status, :to_status, :event, :actor_kind, :actor_id, :on_behalf_of, :reason)"
)
_SYNC = text(
    "UPDATE tax_returns SET sync_status = :sync_status, last_synced_at = :at "
    "WHERE tenant_id = :tenant_id AND work_item_id = :work_item_id"
)


async def status_of(session: AsyncSession, values: Mapping[str, object]) -> tuple[str, int] | None:
    row = (await session.execute(_STATUS, dict(values))).first()
    return None if row is None else (str(row[0]), int(row[1]))


async def move_status(session: AsyncSession, values: Mapping[str, object]) -> bool:
    """One row moved, or none when the version moved first (a stale `seen_version`)."""
    result = await session.execute(_MOVE, dict(values))
    return (getattr(result, "rowcount", 0) or 0) == 1


async def insert_status_event(session: AsyncSession, values: Mapping[str, object]) -> None:
    await session.execute(_EVENT, dict(values))


async def set_sync_state(session: AsyncSession, values: Mapping[str, object]) -> None:
    await session.execute(_SYNC, dict(values))


# T-01-T18: the `tax_final_approval` gate reads the engagement's returns' statuses.
_ON_ENGAGEMENT = text(
    "SELECT status FROM tax_returns WHERE tenant_id = :tenant_id "
    "AND engagement_id = :engagement_id"
)


async def statuses_on(session: AsyncSession, values: Mapping[str, object]) -> list[str]:
    return [str(s) for s in (await session.execute(_ON_ENGAGEMENT, dict(values))).scalars()]
