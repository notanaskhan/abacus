"""The synthetic-only Workbench session recorder (W-02-T13; W-02 §5.3; DEC-4717). Amber. The
scenario loader's one way to put WB-01's rows in place for the Brightwater Hale tenant: a session
as its owner left it (title, origin, state, last activity, client scope and engagement), through
this module's own table, as the owner (a human context), audited `session.recorded_synthetic`. It
refuses every firm that is not synthetic (404), so nothing it writes stands in for a real session.
A row that exists (by its stable id) is left as it is.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.errors import NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.identity.api import AuthContext, is_synthetic_firm


@dataclass(frozen=True)
class SeedSession:
    id: UUID
    title: str
    origin: str  # manual, schedule, trigger, saved_prompt, engagement_run
    state: str  # live, running, awaiting_answer, ready_for_review, complete, failed
    last_item_at: datetime
    client_scope: Sequence[UUID] = ()
    engagement_id: UUID | None = None
    first_message: str | None = None


_INSERT: Final = text(
    "INSERT INTO workbench_sessions (id, tenant_id, title, owner_user_id, origin, state, "
    "context_refs, client_scope, last_item_at, item_seq) VALUES (:id, :t, :title, :me, :origin, "
    ":state, CAST(:refs AS jsonb), :clients, :at, :seq) ON CONFLICT (id) DO NOTHING RETURNING id"
)
_ITEM: Final = text(
    "INSERT INTO session_items (tenant_id, session_id, seq, kind, payload, actor_kind, actor_id, "
    "classification) VALUES (:t, :s, 1, 'user_message', CAST(:payload AS jsonb), 'human', :me, "
    "'confidential')"
)


async def record_synthetic_session(ctx: AuthContext, seed: SeedSession) -> bool:
    """The session as its owner (`ctx`) left it; True when written now."""
    if not await is_synthetic_firm(ctx.tenant):
        raise NotFound("session")
    refs = (
        []
        if seed.engagement_id is None
        else [{"kind": "engagement", "id": str(seed.engagement_id)}]
    )
    async with uow(ctx.tenant) as tx:
        written = await tx.session.scalar(
            _INSERT,
            {
                "id": seed.id, "t": ctx.tenant_id, "title": seed.title, "me": ctx.user_id,
                "origin": seed.origin, "state": seed.state, "refs": json.dumps(refs),
                "clients": list(seed.client_scope), "at": seed.last_item_at,
                "seq": 1 if seed.first_message else 0,
            },
        )  # fmt: skip
        if written is None:
            return False
        if seed.first_message:
            await tx.session.execute(
                _ITEM,
                {
                    "t": ctx.tenant_id, "s": seed.id, "me": str(ctx.user_id),
                    "payload": json.dumps(
                        {"v": 1, "body": seed.first_message, "key": str(seed.id)}
                    ),
                },
            )  # fmt: skip
        tx.record(
            "session.recorded_synthetic",
            target=Target("workbench_session", seed.id),
            after=Ref(owner=ctx.user_id, origin=seed.origin),
        )
    return True


__all__ = ["SeedSession", "record_synthetic_session"]
