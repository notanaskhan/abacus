"""The portal topic of `GET /v1/events` (P-10-T27; DEC-3117): `portal:<grant scope id>` for a
client principal who holds an active grant on that scope (`scope_only`), and for no one else."""

from __future__ import annotations

from typing import cast
from uuid import UUID

from abacus.kernel import realtime
from abacus.modules.identity.api import AuthContext, active_grants


async def portal_topic(ctx: object, ident: str) -> realtime.TopicAccess | None:
    auth = cast(AuthContext, ctx)  # a subscriber: a signed-in person (Member)
    if not auth.client:
        return None
    scope = UUID(ident)
    grants = await active_grants(auth.tenant, auth.user_id)
    return "content" if any(g.scope_id == scope for g in grants) else None


def register() -> None:
    realtime.register_topic("portal", portal_topic)
