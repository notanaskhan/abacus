"""The legacy agent run backfill (P-10-T14; SPEC-647 §4.4; ADR-169, ADR-233).

Rows written before migration 0680 have `state` NULL. One batch, in the firm's own session and one
unit of work, takes up to `limit` of them (oldest first, `FOR UPDATE SKIP LOCKED` so a live writer
is never waited on), and gives each:

- its legacy state: `completed` to `succeeded`, `escalated` to `needs_input` with reason
  `escalated`, `failed` to `failed`, `running` to `running` (0680's mapping; migration 0711's
  triggers accept only that, and keep `status`, `finished_at` and `failure_code`);
- a `run_number` from the firm's `agent_run` counter, in start order, after any v2 numbers;
- a `session_id` where a workbench session item already names the run (asked through the
  port workbench registers, `register_session_links`: agents never reads workbench's tables).

One `agent_runs.backfilled` audit event per batch, by the system, with counts and the first and
last run only. The specialists keep writing `status`; 0680's sync trigger keeps their new rows in
step, so the backfill never races a writer it can't see.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Final
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from temporalio import activity

from abacus.kernel.db import TenantContext
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.agents.run_backfill_workflow import BackfillBatch

_ACTOR: Final = "agent_run_backfill"
COUNTER: Final = "agent_run"
MAX_BATCH: Final = 2_000
_log = get_logger(__name__)

LEGACY_STATE: Final[dict[str, str]] = {
    "completed": "succeeded",
    "escalated": "needs_input",
    "failed": "failed",
    "running": "running",
}


@dataclass(frozen=True)
class BackfillResult:
    updated: int
    remaining: bool
    first_run_id: UUID | None = None
    last_run_id: UUID | None = None


_PICK = text(
    """
    SELECT id, status FROM agent_runs
     WHERE state IS NULL
     ORDER BY started_at, id
     LIMIT :limit
     FOR UPDATE SKIP LOCKED
    """
)
_SEED_COUNTER = text(
    """
    INSERT INTO tenant_counters (tenant_id, name, value)
    SELECT CAST(:tenant AS uuid), :name, COALESCE(max(run_number), 0) FROM agent_runs
    ON CONFLICT (tenant_id, name) DO NOTHING
    """
)
_TAKE_NUMBERS = text(
    "UPDATE tenant_counters SET value = value + :n WHERE name = :name RETURNING value"
)
SessionLinks = Callable[[AsyncSession, Sequence[UUID]], Awaitable[dict[UUID, UUID]]]
_session_links: SessionLinks | None = None


def register_session_links(port: SessionLinks) -> None:
    """Workbench answers which session first named each run, in the caller's session."""
    global _session_links
    _session_links = port


_SET = text(
    """
    UPDATE agent_runs
       SET state = :state,
           state_reason = CASE WHEN :state = 'needs_input' THEN 'escalated' ELSE state_reason END,
           run_number = :run_number,
           session_id = COALESCE(:session_id, session_id)
     WHERE id = :id AND state IS NULL
    """
)
_ANY_LEFT = text("SELECT EXISTS (SELECT 1 FROM agent_runs WHERE state IS NULL)")


def legacy_state(status: str) -> str:
    """0680's mapping; an unknown status is a running legacy run (its CHECK allows no other)."""
    return LEGACY_STATE.get(status, "running")


async def backfill_batch(tenant_id: UUID, limit: int) -> BackfillResult:
    if not 1 <= limit <= MAX_BATCH:
        raise ValueError(f"a backfill batch is 1 to {MAX_BATCH} rows")
    ctx = TenantContext(tenant_id, "system", _ACTOR)
    async with uow(ctx) as tx:
        rows = (await tx.session.execute(_PICK, {"limit": limit})).all()
        if not rows:
            return BackfillResult(0, False)
        ids = [row.id for row in rows]
        await tx.session.execute(_SEED_COUNTER, {"tenant": str(tenant_id), "name": COUNTER})
        top = int(
            (
                await tx.session.execute(_TAKE_NUMBERS, {"n": len(rows), "name": COUNTER})
            ).scalar_one()
        )
        sessions = await _session_links(tx.session, ids) if _session_links is not None else {}
        first_number = top - len(rows) + 1
        for offset, row in enumerate(rows):
            await tx.session.execute(
                _SET,
                {
                    "id": row.id,
                    "state": legacy_state(row.status),
                    "run_number": first_number + offset,
                    "session_id": sessions.get(row.id),
                },
            )
        remaining = bool((await tx.session.execute(_ANY_LEFT)).scalar_one())
        tx.record(
            "agent_runs.backfilled",
            target=Target("agent_run", ids[0]),
            after=Ref(
                count=len(rows),
                first_run=ids[0],
                last_run=ids[-1],
                first_number=first_number,
                last_number=top,
            ),
        )
    _log.info("agent_runs.backfilled", tenant_id=str(tenant_id), count=len(rows))
    return BackfillResult(len(rows), remaining, ids[0], ids[-1])


@activity.defn(name="agents.backfill_run_batch")
async def backfill_run_batch_activity(tenant_id: str, limit: int) -> BackfillBatch:
    result = await backfill_batch(UUID(tenant_id), limit)
    return BackfillBatch(result.updated, result.remaining)
