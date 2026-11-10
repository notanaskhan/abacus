"""The run topic of `GET /v1/events` (P-10-T27; DEC-3117): `run:<id>` for a person who may read
the run (`agent_run.read`, 404 alike for a walled or unknown run)."""

from __future__ import annotations

from typing import cast
from uuid import UUID

from abacus.kernel import realtime
from abacus.kernel.errors import NotFound
from abacus.modules.identity.api import AuthContext, Forbidden


async def run_topic(ctx: object, ident: str) -> realtime.TopicAccess | None:
    from abacus.modules.agents.runs import authorised_run

    auth = cast(AuthContext, ctx)  # a subscriber: a signed-in person (Member)
    if auth.client:
        return None
    try:
        await authorised_run(auth, UUID(ident))
    except (NotFound, Forbidden):
        return None
    return "content"


def register() -> None:
    realtime.register_topic("run", run_topic)
