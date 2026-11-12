"""The session's live thread (TASK-7325; SPEC-647 §3.9; T-04-T37's TAX-08 drawer).

A session item written (the person's message or answer, or a turn's agent items) emits
`session.items_changed` with identifiers only, and the realtime invalidation stream turns it into
an `invalidate` on the session's own topic, `session:<id>`. A subscriber refetches the snapshot
(`GET /v1/workbench/sessions/{id}`), so no item body ever travels on the stream; a tab without
the stream polls. The topic is open to whoever may read the session in full: the session's read
rules, `session.read` on its resource, and a client scope the viewer can open (a locked or
omitted session subscribes to nothing).
"""

from __future__ import annotations

from typing import Annotated, ClassVar, cast
from uuid import UUID

from abacus.kernel import realtime
from abacus.kernel.classification import classified
from abacus.kernel.uow import DomainEvent
from abacus.modules.identity.api import AuthContext


class SessionItemsChanged(DomainEvent):
    """Items were added to a session (identifiers only)."""

    event_type: ClassVar[str] = "session.items_changed"

    session_id: Annotated[UUID, classified("internal")]
    seq: Annotated[int, classified("internal")]


async def session_topic(ctx: object, ident: str) -> realtime.TopicAccess | None:
    from abacus.modules.workbench.sessions import readable_in_full

    auth = cast(AuthContext, ctx)  # a subscriber: a signed-in person (Member)
    if auth.client:
        return None
    try:
        session_id = UUID(ident)
    except ValueError:
        return None
    return "content" if await readable_in_full(auth, session_id) else None


def register() -> None:
    """At the workbench api's import: who may subscribe to `session:<id>`. The invalidation
    itself is notifications' (`notifications.realtime.register`), so the relay's
    `INVALIDATIONS`, composed at that module's import, holds it whatever the import order."""
    realtime.register_topic("session", session_topic)
