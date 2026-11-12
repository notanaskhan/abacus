"""The `todo` search projection (P-02-T07; C15 v1; ADR-241; DEC-4613).

An open to-do on an engagement is found by its title (scrubbed), with its assignee's name and due
date ("Re-request 2 SURL files" · Cole Hart · Sep 28). It opens SHL-17 on the to-do
(`?ov=todos:<id>`), scoped to its engagement. A to-do is never shown as the agent's (the agent is
never an assignee, P-05 AC-19); a done or deleted to-do is not findable.
"""

from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.engagements.api import engagement_hold_facts
from abacus.modules.identity.api import display_names
from abacus.modules.platform.api import (
    SearchIndexDocument,
    SearchProjection,
    register_search_projection,
)

_TODO = text(
    "SELECT id, engagement_id, work_item_id, title, status, assignee_user_id, due_on, "
    "updated_at FROM todos WHERE id = :id AND deleted_at IS NULL AND status = 'open' "
    "AND engagement_id IS NOT NULL"
)
_IDS = text(
    "SELECT id FROM todos WHERE deleted_at IS NULL AND status = 'open' "
    "AND engagement_id IS NOT NULL "
    "AND (CAST(:after AS uuid) IS NULL OR id > CAST(:after AS uuid)) ORDER BY id LIMIT :limit"
)


async def build_todo(tenant: TenantContext, todo_id: UUID) -> SearchIndexDocument | None:
    async with tenant_session(tenant) as session:
        row = (await session.execute(_TODO, {"id": todo_id})).mappings().first()
    if row is None:
        return None
    engagement_id = UUID(str(row["engagement_id"]))
    facts = await engagement_hold_facts(tenant, engagement_id)
    if facts is None:
        return None
    assignee = row["assignee_user_id"]
    names = {} if assignee is None else await display_names([UUID(str(assignee))])
    who = None if assignee is None else names.get(UUID(str(assignee)))
    return SearchIndexDocument(
        object_id=todo_id,
        title=str(row["title"]),
        context=who,
        engagement_id=engagement_id,
        work_item_id=None if row["work_item_id"] is None else UUID(str(row["work_item_id"])),
        client_id=facts.client_id,
        owner_user_id=None if assignee is None else UUID(str(assignee)),
        status_code=str(row["status"]),
        due_on=row["due_on"],
        source_updated_at=row["updated_at"],
        target_params={"todoId": str(todo_id)},
    )


async def todo_ids(tenant: TenantContext, after: UUID | None, limit: int) -> list[UUID]:
    async with tenant_session(tenant) as session:
        rows = await session.execute(_IDS, {"after": after, "limit": limit})
        return [UUID(str(r)) for r in rows.scalars()]


def _todo_of(payload: Mapping[str, object]) -> list[UUID]:
    raw = payload.get("todo_id")
    return [] if raw is None else [UUID(str(raw))]


_EVENTS = ("created", "updated", "completed", "deleted", "assigned", "moved", "reopened")
TODO_PROJECTION = SearchProjection(
    object_type="todo",
    group="todos",
    read_action="todo.read",
    scope_kind="engagement",
    build=build_todo,
    target="SHL-17",
    triggers={f"todo.{e}": _todo_of for e in _EVENTS},
    list_ids=todo_ids,
)
register_search_projection(TODO_PROJECTION)
