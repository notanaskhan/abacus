"""Audit values for requests (G-02-T09 gap; SPEC-349 AC-5, AC-10, AC-11; DEC-60, DEC-459).

ADM-07's values section for events on `request_item` targets, resolved at read time for a viewer
`audit_trail.values` has already let through (flag on, need to know). Facts the event pins only:

- every row's item is the request's title (Confidential), when it has one;
- `client_visible` before and after (the visibility toggle): `true` or `false`, codes the SPA
  words;
- `user_id` before and after (the client assignee): display names (Confidential).

Anything else is `unavailable` ("Values not available"). When the event names an engagement,
the request must belong to it; when it names none (most writers pass no `Scope`), the viewer
must hold `engagement.read` on the request's own engagement (security review M1). Otherwise
`unavailable` (fail closed).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import NotFound
from abacus.modules.identity.api import (
    AuthContext,
    allowed_actions,
    engagement_resource,
    names_of,
)
from abacus.modules.platform.api import AuditEventRef, AuditValueRow, AuditValues

UNAVAILABLE: Final = AuditValues("unavailable")
CONTENT_READ: Final = "engagement.read"
_ITEM = text("SELECT engagement_id, title FROM request_items WHERE id = :id")


def _uuid(value: object) -> UUID | None:
    if value is None:
        return None
    try:
        return UUID(str(value))
    except ValueError:
        return None


async def _may_read(viewer: AuthContext, engagement_id: UUID) -> bool:
    """Security review M1: an event with no engagement of its own is not firm-level content when
    its target belongs to one; the reader must hold that engagement's content read, as
    `audit_trail.values` requires on an engagement event (a probe: no `authz.denied` logged)."""
    try:
        resource = await engagement_resource(viewer.tenant, engagement_id)
    except NotFound:
        return False
    return CONTENT_READ in await allowed_actions(viewer, resource, (CONTENT_READ,))


def _flag(refs: Mapping[str, str | int], key: str) -> str | None:
    value = refs.get(key)
    return None if not isinstance(value, int) else ("true" if value else "false")


async def request_item_values(viewer: AuthContext, event: AuditEventRef) -> AuditValues:
    item_id = _uuid(event.target_id)
    if item_id is None:
        return UNAVAILABLE
    before, after = event.before_ref or {}, event.after_ref or {}
    visible = (_flag(before, "client_visible"), _flag(after, "client_visible"))
    people = (_uuid(before.get("user_id")), _uuid(after.get("user_id")))
    if visible == (None, None) and people == (None, None):
        return UNAVAILABLE
    async with tenant_session(viewer.tenant) as session:
        item = (await session.execute(_ITEM, {"id": item_id})).mappings().first()
    if item is None:
        return UNAVAILABLE
    if event.engagement_id is not None:
        if item["engagement_id"] != event.engagement_id:
            return UNAVAILABLE
    elif not await _may_read(viewer, item["engagement_id"]):
        return UNAVAILABLE  # an unscoped event on this request: its engagement's read decides
    label = str(item["title"] or "")
    rows: list[AuditValueRow] = []
    if visible != (None, None):
        rows.append(
            AuditValueRow(
                field="client_visible",
                item_label=label,
                before=visible[0],
                after=visible[1],
                classification="internal",
            )
        )
    if people != (None, None):
        names = await names_of(sorted({u for u in people if u is not None}, key=str))
        rows.append(
            AuditValueRow(
                field="client_assignee",
                item_label=label,
                before=names.get(people[0]) if people[0] is not None else None,
                after=names.get(people[1]) if people[1] is not None else None,
                classification="confidential",
            )
        )
    return AuditValues("resolved", rows=tuple(rows))


__all__ = ["request_item_values"]
