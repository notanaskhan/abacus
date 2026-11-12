"""The `inbox_thread` search projection (P-02-T07; C15 v1; ADR-241; DEC-4613).

A matched inbox thread is found by its subject (scrubbed: hostile characters, TINs and amounts
removed) and its sender's display name, with its client's name as the context. Unmatched threads
belong to no client and are not findable until matched (walls bite on `client_id`). It opens
INB-01 on the thread.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast
from uuid import UUID

from sqlalchemy import Column, literal, select, text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.organisations.api import client_name_column
from abacus.modules.platform.api import (
    RelatedParty,
    SearchIndexDocument,
    SearchProjection,
    register_search_projection,
)

_THREAD = text(
    "SELECT id, client_id, subject_display, sender_display, last_received_at, ignored_reason "
    "FROM inbox_threads WHERE id = :id AND client_id IS NOT NULL"
)
_IDS = text(
    "SELECT id FROM inbox_threads WHERE client_id IS NOT NULL "
    "AND (CAST(:after AS uuid) IS NULL OR id > CAST(:after AS uuid)) ORDER BY id LIMIT :limit"
)


async def build_inbox_thread(tenant: TenantContext, thread_id: UUID) -> SearchIndexDocument | None:
    async with tenant_session(tenant) as session:
        row = (await session.execute(_THREAD, {"id": thread_id})).mappings().first()
        if row is None or row["ignored_reason"] is not None:
            return None
        client_id = UUID(str(row["client_id"]))
        name = await session.scalar(
            select(client_name_column(cast(Column[UUID], literal(client_id))))
        )
    sender = row["sender_display"]
    return SearchIndexDocument(
        object_id=thread_id,
        title=str(row["subject_display"] or "(no subject)"),
        context=None if name is None else str(name),
        client_id=client_id,
        related=() if not sender else (RelatedParty(name=str(sender), label="sender"),),
        status_code="waiting",
        source_updated_at=row["last_received_at"],
        target_params={"threadId": str(thread_id)},
    )


async def inbox_thread_ids(tenant: TenantContext, after: UUID | None, limit: int) -> list[UUID]:
    async with tenant_session(tenant) as session:
        rows = await session.execute(_IDS, {"after": after, "limit": limit})
        return [UUID(str(r)) for r in rows.scalars()]


def _thread_of(payload: Mapping[str, object]) -> list[UUID]:
    raw = payload.get("thread_id")
    return [] if raw is None else [UUID(str(raw))]


INBOX_THREAD_PROJECTION = SearchProjection(
    object_type="inbox_thread",
    group="inbox",
    read_action="inbox.read",
    scope_kind="client",
    build=build_inbox_thread,
    target="INB-01",
    triggers={"inbox_attachment.received": _thread_of},
    list_ids=inbox_thread_ids,
)
register_search_projection(INBOX_THREAD_PROJECTION)
