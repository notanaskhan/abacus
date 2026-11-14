"""The `drill` session item's write (W-02-T20; W-02 §3.8; DEC-4933; ADR-008). Amber.

`agents.run_artifacts.drill` lists a result group's records by code; the item it becomes lives in
the session's own tables, so workbench writes it (agents may not touch them; OWN-001). Workbench
registers this writer with agents at import.

- Idempotent: the same key hash answers the item already appended, to the owner only.
- Only the session's owner appends; any other viewer gets 404 (no existence leak, DEC-43).
- The payload holds references only; names resolve again at read time (DEC-61).
"""

from __future__ import annotations

import json
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.identity.api import AuthContext
from abacus.modules.workbench.session_events import SessionItemsChanged

_LOCK: Final = text(
    "SELECT item_seq, owner_user_id FROM workbench_sessions WHERE id = :id AND deleted_at IS NULL "
    "FOR UPDATE"
)
_BY_KEY: Final = text(
    "SELECT i.id FROM session_items i JOIN workbench_sessions w ON w.id = i.session_id "
    "WHERE i.session_id = :s AND i.kind = 'drill' AND i.payload->>'key' = :key "
    "AND w.owner_user_id = :me AND w.deleted_at IS NULL LIMIT 1"
)


async def append_drill(
    ctx: AuthContext, session_id: UUID, key_hash: str, payload: dict[str, object]
) -> UUID:
    """The `drill` item's id: the one already appended under `key_hash`, else a new one."""
    async with tenant_session(ctx.tenant) as session:
        again = await session.scalar(
            _BY_KEY, {"s": session_id, "key": key_hash, "me": ctx.user_id}
        )
    if again is not None:
        return cast(UUID, again)
    async with uow(ctx.tenant) as tx:
        locked = (await tx.session.execute(_LOCK, {"id": session_id})).first()
        if locked is None or locked.owner_user_id != ctx.user_id:
            raise NotFound("session")
        seq = int(locked.item_seq) + 1
        item_id = cast(
            UUID,
            await tx.session.scalar(
                text(
                    "INSERT INTO session_items (tenant_id, session_id, seq, kind, payload, "
                    "actor_kind, actor_id, classification) VALUES (:t, :s, :seq, 'drill', "
                    "CAST(:payload AS jsonb), 'human', :me, 'confidential') RETURNING id"
                ),
                {
                    "t": ctx.tenant_id,
                    "s": session_id,
                    "seq": seq,
                    "payload": json.dumps(payload | {"key": key_hash}),
                    "me": str(ctx.user_id),
                },
            ),
        )
        await tx.session.execute(
            text(
                "UPDATE workbench_sessions SET item_seq = :seq, last_item_at = clock_timestamp() "
                "WHERE id = :id"
            ),
            {"seq": seq, "id": session_id},
        )
        tx.record(
            "session.drill_appended",
            target=Target("workbench_session", session_id),
            after=Ref(seq=seq, artifact=str(payload.get("artifact_id"))),
        )
        tx.emit(SessionItemsChanged(session_id=session_id, seq=seq))
    return item_id


__all__ = ["append_drill"]
