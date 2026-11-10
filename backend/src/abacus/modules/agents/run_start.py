"""Open a runtime-v2 capability run for a person (T-04-T25; SPEC-647 §3.4; ADR-005). PROTECTED.

A capability with its own workflow (the first: `tax.return_drafter`) is started by its owner's
service for a person who may start runs on the engagement (`agent_run.start`, Senior and up on the
team; agent and system deny). This writes the run's row with its v2 columns (the spec's version
and task scope, the next run number from the firm's `agent_run` counter, `queued`, as the person
it runs for) and one `agent_run.started` audit event; the owner then dispatches its workflow.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.uow import Ref, Scope, Target, uow
from abacus.modules.agents.spec_v2 import spec_v2
from abacus.modules.engagements.api import get_ref
from abacus.modules.identity.api import AuthContext, Forbidden, authorise

COUNTER: Final = "agent_run"
_SEED = text(
    "INSERT INTO tenant_counters (tenant_id, name, value) SELECT CAST(:t AS uuid), :name, "
    "COALESCE(max(run_number), 0) FROM agent_runs ON CONFLICT (tenant_id, name) DO NOTHING"
)
_NEXT = text("UPDATE tenant_counters SET value = value + 1 WHERE name = :name RETURNING value")
_RUN = text(
    "INSERT INTO agent_runs (tenant_id, agent_id, spec_version, engagement_id, "
    "initiator_user_id, task_scope, state, mode, trigger_kind, run_number, runs_as_user_id, "
    "inputs, work_item_ref) VALUES (:t, :agent, :version, :eng, :by, :scope, 'queued', 'run', "
    "'manual', :number, :by, CAST(:inputs AS jsonb), :work_item) RETURNING id"
)


async def open_capability_run(
    ctx: AuthContext,
    *,
    agent_id: str,
    engagement_id: UUID,
    inputs: Mapping[str, object],
    work_item_ref: str | None = None,
) -> UUID:
    """The run's row for `ctx` (module docstring); the caller dispatches its workflow."""
    if ctx.tenant.actor_kind != "human" or ctx.client or ctx.is_support:
        raise Forbidden("agent_run.start", "role")
    spec = spec_v2(agent_id)
    ref = await get_ref(ctx, engagement_id)  # a wall answers 404
    await authorise(ctx, "agent_run.start", ref.resource())
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(_SEED, {"t": ctx.tenant_id, "name": COUNTER})
        number = cast(int, await tx.session.scalar(_NEXT, {"name": COUNTER}))
        run_id = cast(
            UUID,
            await tx.session.scalar(
                _RUN,
                {
                    "t": ctx.tenant_id,
                    "agent": spec.id,
                    "version": spec.version,
                    "eng": engagement_id,
                    "by": ctx.user_id,
                    "scope": sorted(spec.task_scope),
                    "number": number,
                    "inputs": json.dumps(dict(inputs), sort_keys=True, default=str),
                    "work_item": work_item_ref,
                },
            ),
        )
        tx.record(
            "agent_run.started",
            target=Target("agent_run", run_id),
            after=Ref(initiator=ctx.user_id, run_number=number),
            scope=Scope(engagement_id=engagement_id),
        )
    return run_id


__all__ = ["open_capability_run"]
