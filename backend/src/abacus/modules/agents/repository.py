"""Agents data access: agent runs and screening results only (ADR-008, ADR-103)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import func, insert, select, update
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.modules.agents.models import AgentRun, ScreeningResult
from abacus.modules.identity.api import AuthContext, visible


async def insert_run(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: str,
    spec_version: int,
    engagement_id: UUID,
    evidence_version_id: UUID | None,
    initiator_user_id: UUID,
    source_event_id: UUID | None,
    task_scope: list[str],
) -> UUID | None:
    """The new run's ID, or None if this agent already ran for this event."""
    return (
        await session.execute(
            pg_insert(AgentRun)
            .values(
                id=uuid4(),
                tenant_id=tenant_id,
                agent_id=agent_id,
                spec_version=spec_version,
                engagement_id=engagement_id,
                evidence_version_id=evidence_version_id,
                initiator_user_id=initiator_user_id,
                source_event_id=source_event_id,
                task_scope=task_scope,
            )
            .on_conflict_do_nothing(constraint="agent_runs_once_per_event")
            .returning(AgentRun.id)
        )
    ).scalar_one_or_none()


async def run_for_event(
    session: AsyncSession, agent_id: str, source_event_id: UUID
) -> AgentRun | None:
    return (
        await session.execute(
            select(AgentRun).where(
                AgentRun.agent_id == agent_id, AgentRun.source_event_id == source_event_id
            )
        )
    ).scalar_one_or_none()


async def get_run(session: AsyncSession, run_id: UUID) -> AgentRun | None:
    return (
        await session.execute(select(AgentRun).where(AgentRun.id == run_id))
    ).scalar_one_or_none()


async def lock_run(session: AsyncSession, run_id: UUID) -> AgentRun | None:
    return (
        await session.execute(select(AgentRun).where(AgentRun.id == run_id).with_for_update())
    ).scalar_one_or_none()


async def set_queued(
    session: AsyncSession, run_id: UUID, reason: str | None, estimated_start_at: datetime | None
) -> None:
    """Mark a running run as waiting for a work slot (`reason`), or running again (None)."""
    await session.execute(
        update(AgentRun)
        .where(AgentRun.id == run_id, AgentRun.status == "running")
        .values(queued_reason=reason, estimated_start_at=estimated_start_at)
    )


async def finish_run(
    session: AsyncSession,
    run_id: UUID,
    *,
    status: str,
    context_hash: str | None = None,
    output: dict[str, object] | None = None,
    failure_code: str | None = None,
) -> bool:
    """True if this call ended the run (it was running)."""
    result = await session.execute(
        update(AgentRun)
        .where(AgentRun.id == run_id, AgentRun.status == "running")
        .values(
            status=status,
            context_hash=context_hash,
            output=output,
            failure_code=failure_code,
            finished_at=datetime.now(UTC),
            # A run that ends is no longer waiting (CHECK agent_runs_queued_running).
            queued_reason=None,
            estimated_start_at=None,
        )
        .returning(AgentRun.id)
    )
    return result.scalar_one_or_none() is not None


async def try_lock_run(session: AsyncSession, run_id: UUID) -> bool:
    """Take the run's advisory lock until this transaction ends; False if another holds it."""
    key = func.hashtextextended(f"agent_run:{run_id}", 0)
    return bool((await session.execute(select(func.pg_try_advisory_xact_lock(key)))).scalar_one())


async def result_for_run(session: AsyncSession, run_id: UUID) -> UUID | None:
    return (
        await session.execute(
            select(ScreeningResult.id).where(ScreeningResult.agent_run_id == run_id)
        )
    ).scalar_one_or_none()


async def insert_screening_result(session: AsyncSession, *, values: dict[str, object]) -> UUID:
    result_id = uuid4()
    await session.execute(insert(ScreeningResult).values(id=result_id, **values))
    return result_id


async def latest_result_for_version(
    session: AsyncSession, evidence_version_id: UUID
) -> ScreeningResult | None:
    """The newest screening result about one version (the caller authorised on its engagement)."""
    return (
        await session.execute(
            select(ScreeningResult)
            .where(ScreeningResult.evidence_version_id == evidence_version_id)
            .order_by(ScreeningResult.created_at.desc(), ScreeningResult.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def latest_results(
    session: AsyncSession, ctx: AuthContext, engagement_id: UUID
) -> Sequence[ScreeningResult]:
    """The latest screening result of each evidence version of the engagement the caller may
    read (a version re-screened by a later event shows its newest result)."""
    return (
        (
            await session.execute(
                select(ScreeningResult)
                .where(
                    ScreeningResult.engagement_id == engagement_id,
                    visible(ctx, "evidence.read", ScreeningResult.engagement_id),
                )
                .ext(distinct_on(ScreeningResult.evidence_version_id))
                .order_by(
                    ScreeningResult.evidence_version_id,
                    ScreeningResult.created_at.desc(),
                    ScreeningResult.id.desc(),
                )
            )
        )
        .scalars()
        .all()
    )
