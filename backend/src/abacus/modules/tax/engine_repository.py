"""Engine-bridge data access (T-01-T19; migration 0465): links, sync events, import diffs and
diagnostics. Text SQL in the caller's session; every statement runs under row-level security."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import Row, text
from sqlalchemy.ext.asyncio import AsyncSession

TextRow = Row[Any]  # a text query's row, read by column name


async def link_of(session: AsyncSession, return_id: UUID) -> TextRow | None:
    return (
        await session.execute(
            text(
                "SELECT id, engine_return_id, version FROM engine_return_links "
                "WHERE return_id = :r AND engine = 'cch_axcess' FOR UPDATE"
            ),
            {"r": return_id},
        )
    ).first()


async def insert_link(
    session: AsyncSession, tenant_id: UUID, return_id: UUID, engine_return_id: str
) -> None:
    await session.execute(
        text(
            "INSERT INTO engine_return_links (tenant_id, return_id, engine, engine_return_id) "
            "VALUES (:t, :r, 'cch_axcess', :e)"
        ),
        {"t": tenant_id, "r": return_id, "e": engine_return_id},
    )


async def set_link_version(session: AsyncSession, return_id: UUID, version: int) -> None:
    await session.execute(
        text(
            "UPDATE engine_return_links SET version = :v "
            "WHERE return_id = :r AND engine = 'cch_axcess' AND version < :v"
        ),
        {"r": return_id, "v": version},
    )


async def insert_event(session: AsyncSession, values: Mapping[str, object]) -> UUID:
    row = dict(values)
    row["summary"] = json.dumps(row.get("summary") or {})
    for key in ("engine_return_id", "version", "file_name", "file_key", "file_version"):
        row.setdefault(key, None)
    for key in ("file_size", "payload_sha256", "actor_user_id"):
        row.setdefault(key, None)
    return (
        await session.execute(
            text(
                "INSERT INTO engine_sync_events (tenant_id, return_id, kind, engine_return_id, "
                "version, file_name, file_key, file_version, file_size, payload_sha256, "
                "actor_user_id, summary) VALUES (:tenant_id, :return_id, :kind, "
                ":engine_return_id, :version, :file_name, :file_key, :file_version, "
                ":file_size, :payload_sha256, :actor_user_id, CAST(:summary AS jsonb)) "
                "RETURNING id"
            ),
            row,
        )
    ).scalar_one()


async def events_of(session: AsyncSession, return_id: UUID) -> Sequence[TextRow]:
    return (
        await session.execute(
            text(
                "SELECT id, kind, engine_return_id, version, actor_user_id, at, summary "
                "FROM engine_sync_events WHERE return_id = :r ORDER BY at DESC, id"
            ),
            {"r": return_id},
        )
    ).all()


async def insert_diff(session: AsyncSession, values: Mapping[str, object]) -> UUID:
    row = {**values, "rows": json.dumps(values["rows"])}
    return (
        await session.execute(
            text(
                "INSERT INTO engine_import_diffs (tenant_id, return_id, sync_event_id, "
                "checkpoint_id, engine_return_id, version, rows) VALUES (:tenant_id, "
                ":return_id, :sync_event_id, :checkpoint_id, :engine_return_id, :version, "
                "CAST(:rows AS jsonb)) RETURNING id"
            ),
            row,
        )
    ).scalar_one()


_BY_ID = text(
    "SELECT d.id, d.return_id, d.sync_event_id, d.checkpoint_id, d.approved_checkpoint_id, "
    "d.engine_return_id, d.version, d.rows, d.status, d.row_version, e.at AS uploaded_at "
    "FROM engine_import_diffs d JOIN engine_sync_events e ON e.id = d.sync_event_id "
    "WHERE d.id = :i"
)
_BY_ID_LOCKED = text(
    "SELECT d.id, d.return_id, d.sync_event_id, d.checkpoint_id, d.approved_checkpoint_id, "
    "d.engine_return_id, d.version, d.rows, d.status, d.row_version, e.at AS uploaded_at "
    "FROM engine_import_diffs d JOIN engine_sync_events e ON e.id = d.sync_event_id "
    "WHERE d.id = :i FOR UPDATE OF d"
)
_PENDING = text(
    "SELECT d.id, d.return_id, d.sync_event_id, d.checkpoint_id, d.approved_checkpoint_id, "
    "d.engine_return_id, d.version, d.rows, d.status, d.row_version, e.at AS uploaded_at "
    "FROM engine_import_diffs d JOIN engine_sync_events e ON e.id = d.sync_event_id "
    "WHERE d.return_id = :r AND d.status = 'pending_approval' LIMIT 1"
)


async def diff_of(
    session: AsyncSession, import_id: UUID, *, lock: bool = False
) -> TextRow | None:  # a text query's row
    return (await session.execute(_BY_ID_LOCKED if lock else _BY_ID, {"i": import_id})).first()


async def pending_of(session: AsyncSession, return_id: UUID) -> TextRow | None:  # a text row
    return (await session.execute(_PENDING, {"r": return_id})).first()


async def decide_diff(
    session: AsyncSession,
    import_id: UUID,
    *,
    status: str,
    approved_checkpoint_id: UUID | None,
    decided_by: UUID,
) -> None:
    await session.execute(
        text(
            "UPDATE engine_import_diffs SET status = :s, approved_checkpoint_id = :c, "
            "decided_by = :u, decided_at = abacus_now(), row_version = row_version + 1 "
            "WHERE id = :i"
        ),
        {"i": import_id, "s": status, "c": approved_checkpoint_id, "u": decided_by},
    )


async def insert_diagnostics(session: AsyncSession, rows: Sequence[Mapping[str, object]]) -> None:
    if rows:
        await session.execute(
            text(
                "INSERT INTO engine_diagnostics (tenant_id, return_id, sync_event_id, code, "
                "severity, field_key, message_text) VALUES (:tenant_id, :return_id, "
                ":sync_event_id, :code, :severity, :field_key, :message_text)"
            ),
            list(rows),
        )


async def diagnostics_of(session: AsyncSession, sync_event_id: UUID) -> Sequence[TextRow]:
    return (
        await session.execute(
            text(
                "SELECT code, severity, field_key, message_text, issue_id FROM "
                "engine_diagnostics WHERE sync_event_id = :e ORDER BY severity, code"
            ),
            {"e": sync_event_id},
        )
    ).all()
