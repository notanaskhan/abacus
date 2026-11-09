"""The engagement and work-item topics of `GET /v1/events` (P-10-T27; DEC-3117).

`engagement:<id>` and `work_item:<id>`: content for a person who may read the engagement
(`engagement.read`, walls included, 404 alike), metadata for a firm admin, who keeps ADM-07's
metadata view (AC-T9); a client principal never (portal topics are the portal's).
"""

from __future__ import annotations

from dataclasses import replace
from typing import cast
from uuid import UUID

from abacus.kernel import realtime
from abacus.kernel.errors import NotFound
from abacus.modules.identity.api import AuthContext, Forbidden, allowed_actions


async def _engagement_access(
    ctx: AuthContext, engagement_id: UUID, work_item_id: UUID | None
) -> realtime.TopicAccess | None:
    from abacus.modules.engagements.api import get_ref

    if ctx.client:
        return None
    try:
        ref = await get_ref(ctx, engagement_id)
    except (NotFound, Forbidden):
        return None
    resource = (
        ref.resource()
        if work_item_id is None
        else replace(ref.resource(), work_item_id=work_item_id)
    )
    held = await allowed_actions(ctx, resource, ["engagement.read"])
    if "engagement.read" in held:
        return "content"
    return "metadata" if ctx.firm_role == "firm_admin" else None


async def engagement_topic(ctx: object, ident: str) -> realtime.TopicAccess | None:
    return await _engagement_access(cast(AuthContext, ctx), UUID(ident), None)


async def work_item_topic(ctx: object, ident: str) -> realtime.TopicAccess | None:
    from abacus.modules.engagements.api import work_item_engagement

    auth = cast(AuthContext, ctx)
    engagement_id = await work_item_engagement(auth.tenant, UUID(ident))
    if engagement_id is None:
        return None
    return await _engagement_access(auth, engagement_id, UUID(ident))


def register() -> None:
    realtime.register_topic("engagement", engagement_topic)
    realtime.register_topic("work_item", work_item_topic)
