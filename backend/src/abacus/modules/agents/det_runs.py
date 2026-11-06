"""A deterministic run's record (A-06-T16's seam; A-06 §6): no model is called, and the run names
the person it acts for, so the work reads as that person via Agent. In the caller's unit of
work, and never a model call."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import UnitOfWork
from abacus.modules.agents.repository import finish_run


@dataclass(frozen=True)
class RunFacts:
    engagement_id: UUID
    initiator: UUID


async def deterministic_run_facts(tenant: TenantContext, run_id: UUID) -> RunFacts:
    async with tenant_session(tenant) as session:
        found = (
            await session.execute(
                text("SELECT engagement_id, initiator_user_id FROM agent_runs WHERE id = :id"),
                {"id": run_id},
            )
        ).first()
    if found is None:
        raise NotFound("agent_run")
    return RunFacts(UUID(str(found.engagement_id)), UUID(str(found.initiator_user_id)))


async def open_deterministic_run(
    tx: UnitOfWork,
    *,
    tenant_id: UUID,
    agent_id: str,
    engagement_id: UUID,
    initiator: UUID,
    task_scope: tuple[str, ...],
) -> UUID:
    run_id = (
        await tx.session.execute(
            text(
                "INSERT INTO agent_runs (tenant_id, agent_id, spec_version, engagement_id, "
                "initiator_user_id, task_scope) VALUES (:t, :a, 1, :e, :i, :s) RETURNING id"
            ),
            {
                "t": tenant_id,
                "a": agent_id,
                "e": engagement_id,
                "i": initiator,
                "s": list(task_scope),
            },
        )
    ).scalar_one()
    return UUID(str(run_id))


async def close_deterministic_run(
    tx: UnitOfWork,
    run_id: UUID,
    *,
    output: dict[str, Any] | None = None,  # Any: the run's JSON; identifiers only
    failure_code: str | None = None,
) -> bool:
    """True if this call ended the run: a retried activity leaves a finished run as it was."""
    return await finish_run(
        tx.session,
        run_id,
        status="failed" if failure_code else "completed",
        output=output,
        failure_code=failure_code,
    )
