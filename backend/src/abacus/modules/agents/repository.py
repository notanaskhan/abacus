"""Agents data access: agent runs and screening results only (ADR-008, ADR-103)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from sqlalchemy import func, insert, select, update
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.modules.agents.models import (
    AgentActivity,
    AgentRun,
    EngagementAgentState,
    KnowledgeChunk,
    KnowledgeDocument,
    Reminder,
    ReminderItem,
    ScreeningResult,
)
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


async def runs_since(
    session: AsyncSession, agent_id: str, engagement_id: UUID, since: datetime
) -> int:
    """The agent's runs for the engagement since `since` (the action cap, SPEC-007)."""
    count = await session.scalar(
        select(func.count())
        .select_from(AgentRun)
        .where(
            AgentRun.agent_id == agent_id,
            AgentRun.engagement_id == engagement_id,
            AgentRun.started_at >= since,
        )
    )
    return count or 0


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


# --- Knowledge (SPEC-009) ----------------------------------------------------------------------


async def firm_chunk_count(session: AsyncSession) -> int:
    """Chunks of the firm's documents that count against its limit (all but withdrawn)."""
    count = await session.scalar(
        select(func.count())
        .select_from(KnowledgeChunk)
        .join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
        .where(KnowledgeDocument.status != "withdrawn")
    )
    return count or 0


async def active_document_with(session: AsyncSession, fingerprint: str) -> UUID | None:
    return (
        await session.execute(
            select(KnowledgeDocument.id).where(
                KnowledgeDocument.fingerprint == fingerprint,
                KnowledgeDocument.status != "withdrawn",
            )
        )
    ).scalar_one_or_none()


async def insert_document(session: AsyncSession, values: dict[str, object]) -> None:
    await session.execute(insert(KnowledgeDocument).values(**values))


async def insert_chunks(session: AsyncSession, rows: list[dict[str, object]]) -> None:
    if rows:
        await session.execute(insert(KnowledgeChunk), rows)


async def lock_document(session: AsyncSession, document_id: UUID) -> KnowledgeDocument | None:
    return (
        await session.execute(
            select(KnowledgeDocument).where(KnowledgeDocument.id == document_id).with_for_update()
        )
    ).scalar_one_or_none()


async def get_document(session: AsyncSession, document_id: UUID) -> KnowledgeDocument | None:
    return (
        await session.execute(select(KnowledgeDocument).where(KnowledgeDocument.id == document_id))
    ).scalar_one_or_none()


async def set_document_status(
    session: AsyncSession,
    document_id: UUID,
    status: str,
    *,
    failure_code: str | None = None,
    withdrawn: bool = False,
) -> None:
    values: dict[str, object] = {"status": status, "failure_code": failure_code}
    if withdrawn:
        values["withdrawn_at"] = func.clock_timestamp()
    await session.execute(
        update(KnowledgeDocument).where(KnowledgeDocument.id == document_id).values(**values)
    )


async def list_documents(
    session: AsyncSession, model: str
) -> Sequence[tuple[KnowledgeDocument, int, int]]:
    """Every document of the firm with its chunk count and how many carry the current model."""
    current = func.count(KnowledgeChunk.position).filter(KnowledgeChunk.embedding_model == model)
    rows = await session.execute(
        select(KnowledgeDocument, func.count(KnowledgeChunk.position), current)
        .outerjoin(KnowledgeChunk, KnowledgeChunk.document_id == KnowledgeDocument.id)
        .group_by(KnowledgeDocument.id)
        .order_by(KnowledgeDocument.created_at.desc(), KnowledgeDocument.id)
    )
    return [(d, total, on_model) for d, total, on_model in rows.all()]


async def chunks_without_vectors(
    session: AsyncSession, document_id: UUID, limit: int
) -> Sequence[KnowledgeChunk]:
    return (
        (
            await session.execute(
                select(KnowledgeChunk)
                .where(
                    KnowledgeChunk.document_id == document_id, KnowledgeChunk.embedding.is_(None)
                )
                .order_by(KnowledgeChunk.position)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )


async def store_vectors(
    session: AsyncSession,
    document_id: UUID,
    vectors: dict[int, tuple[float, ...]],
    model: str,
) -> int:
    """Write each chunk's vector once (null to value); returns how many were written."""
    written = 0
    for position, vector in vectors.items():
        result = await session.execute(
            update(KnowledgeChunk)
            .where(
                KnowledgeChunk.document_id == document_id,
                KnowledgeChunk.position == position,
                KnowledgeChunk.embedding.is_(None),
            )
            .values(
                embedding=list(vector),
                embedding_model=model,
                embedded_at=func.clock_timestamp(),
            )
            .returning(KnowledgeChunk.position)
        )
        written += 1 if result.scalar_one_or_none() is not None else 0
    return written


async def remaining_chunks(session: AsyncSession, document_id: UUID) -> int:
    count = await session.scalar(
        select(func.count())
        .select_from(KnowledgeChunk)
        .where(KnowledgeChunk.document_id == document_id, KnowledgeChunk.embedding.is_(None))
    )
    return count or 0


async def nearest_chunks(
    session: AsyncSession, tenant_id: UUID, query: tuple[float, ...], model: str, k: int
) -> Sequence[tuple[KnowledgeChunk, str, float]]:
    """Exact cosine search over the firm's ready chunks on the current model (Q1: no ANN index,
    nothing shared across tenants). The tenant is explicit as well as enforced by RLS (AC-9)."""
    distance = KnowledgeChunk.embedding.cosine_distance(list(query))
    rows = await session.execute(
        select(KnowledgeChunk, KnowledgeDocument.title, distance)
        .join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
        .where(
            KnowledgeChunk.tenant_id == tenant_id,
            KnowledgeDocument.tenant_id == tenant_id,
            KnowledgeDocument.status == "ready",
            KnowledgeChunk.embedding_model == model,
        )
        .order_by(distance, KnowledgeChunk.document_id, KnowledgeChunk.position)
        .limit(k)
    )
    return [(chunk, title, float(d)) for chunk, title, d in rows.all()]


# --- The engagement agent (SPEC-027; TASK-050) ---------------------------------------------------


async def agent_state(session: AsyncSession, engagement_id: UUID) -> EngagementAgentState | None:
    return (
        await session.execute(
            select(EngagementAgentState).where(EngagementAgentState.engagement_id == engagement_id)
        )
    ).scalar_one_or_none()


async def set_agent_paused(
    session: AsyncSession,
    tenant_id: UUID,
    engagement_id: UUID,
    by: UUID | None,
    reason: str | None,
) -> None:
    paused_at = datetime.now(UTC) if by is not None else None
    await session.execute(
        pg_insert(EngagementAgentState)
        .values(
            tenant_id=tenant_id,
            engagement_id=engagement_id,
            paused_at=paused_at,
            paused_by=by,
            reason=reason,
        )
        .on_conflict_do_update(
            index_elements=["tenant_id", "engagement_id"],
            set_={
                "paused_at": paused_at,
                "paused_by": by,
                "reason": reason,
                "updated_at": func.now(),
            },
        )
    )


async def record_activity(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    engagement_id: UUID,
    policy: str,
    policy_version: int,
    action: str,
    outcome: str,
    reason: str | None = None,
    record_type: str | None = None,
    record_id: UUID | None = None,
    item_count: int | None = None,
    for_user: UUID | None = None,
    source_event_id: UUID | None = None,
) -> bool:
    """One feed row; False when this policy already recorded this event (a redelivery)."""
    found = await session.execute(
        pg_insert(AgentActivity)
        .values(
            tenant_id=tenant_id,
            engagement_id=engagement_id,
            policy=policy,
            policy_version=policy_version,
            action=action,
            outcome=outcome,
            reason=reason,
            record_type=record_type,
            record_id=record_id,
            item_count=item_count,
            for_user=for_user,
            source_event_id=source_event_id,
        )
        .on_conflict_do_nothing()
        .returning(AgentActivity.id)
    )
    return found.scalar_one_or_none() is not None


async def activity_page(
    session: AsyncSession,
    ctx: AuthContext,
    engagement_id: UUID,
    before: datetime | None,
    limit: int,
) -> Sequence[AgentActivity]:
    query = (
        select(AgentActivity)
        .where(
            visible(ctx, "activity.read", AgentActivity.engagement_id),
            AgentActivity.engagement_id == engagement_id,
        )
        .order_by(AgentActivity.created_at.desc(), AgentActivity.id.desc())
        .limit(limit)
    )
    if before is not None:
        query = query.where(AgentActivity.created_at < before)
    return (await session.execute(query)).scalars().all()


async def last_resume_check(session: AsyncSession, engagement_id: UUID) -> datetime | None:
    """When the agent last looked after a resume: earlier skips were replayed then."""
    return await session.scalar(
        select(func.max(AgentActivity.created_at)).where(
            AgentActivity.engagement_id == engagement_id,
            AgentActivity.action == "agent.resume_checked",
            AgentActivity.outcome == "done",
        )
    )


async def screenings_skipped_while_paused(
    session: AsyncSession, engagement_id: UUID, since: datetime
) -> Sequence[AgentActivity]:
    """P-1 rows skipped because the agent was paused, to screen once on resume (AC-6). For the
    agent itself, which acts on the engagement it serves (LIST_EXEMPT)."""
    return (
        (
            await session.execute(
                select(AgentActivity).where(
                    AgentActivity.engagement_id == engagement_id,
                    AgentActivity.policy == "P-1",
                    AgentActivity.outcome == "skipped",
                    AgentActivity.reason.in_(("paused", "firm_paused")),
                    AgentActivity.created_at >= since,
                )
            )
        )
        .scalars()
        .all()
    )


# --- Reminders (SPEC-027 P-4; TASK-051) ----------------------------------------------------------


async def reminder_history(
    session: AsyncSession, item_ids: Sequence[UUID]
) -> Sequence[tuple[UUID, date, int, datetime]]:
    """Each item's reminders that weren't dismissed: (item, due date then, sequence, when), for the
    agent's cadence on the engagement it serves (LIST_EXEMPT)."""
    if not item_ids:
        return []
    rows = await session.execute(
        select(
            ReminderItem.request_item_id,
            ReminderItem.due_on,
            ReminderItem.sequence,
            Reminder.created_at,
        )
        .join(Reminder, Reminder.id == ReminderItem.reminder_id)
        .where(ReminderItem.request_item_id.in_(item_ids), Reminder.status != "dismissed")
    )
    return [(i, d, n, at) for i, d, n, at in rows.all()]


async def insert_reminder(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    engagement_id: UUID,
    recipient_user_id: UUID,
    status: str,
    agent_run_id: UUID | None,
    items: Sequence[tuple[UUID, date, int]],
) -> UUID:
    reminder_id = (
        await session.execute(
            insert(Reminder)
            .values(
                tenant_id=tenant_id,
                engagement_id=engagement_id,
                recipient_user_id=recipient_user_id,
                status=status,
                agent_run_id=agent_run_id,
            )
            .returning(Reminder.id)
        )
    ).scalar_one()
    for item_id, due_on, sequence in items:
        await session.execute(
            insert(ReminderItem).values(
                tenant_id=tenant_id,
                reminder_id=reminder_id,
                request_item_id=item_id,
                due_on=due_on,
                sequence=sequence,
            )
        )
    return reminder_id


async def drafted_reminders(
    session: AsyncSession, engagement_id: UUID
) -> Sequence[tuple[Reminder, Sequence[UUID]]]:
    """One engagement's drafts, after `authorise(follow_up.draft)` on it (LIST_EXEMPT)."""
    rows = (
        (
            await session.execute(
                select(Reminder)
                .where(Reminder.engagement_id == engagement_id, Reminder.status == "drafted")
                .order_by(Reminder.created_at, Reminder.id)
            )
        )
        .scalars()
        .all()
    )
    found: list[tuple[Reminder, Sequence[UUID]]] = []
    for row in rows:
        items = (
            (
                await session.execute(
                    select(ReminderItem.request_item_id).where(ReminderItem.reminder_id == row.id)
                )
            )
            .scalars()
            .all()
        )
        found.append((row, items))
    return found


async def lock_reminder(
    session: AsyncSession, engagement_id: UUID, reminder_id: UUID
) -> Reminder | None:
    return (
        await session.execute(
            select(Reminder)
            .where(Reminder.id == reminder_id, Reminder.engagement_id == engagement_id)
            .with_for_update()
        )
    ).scalar_one_or_none()


async def settle_reminder(
    session: AsyncSession, reminder_id: UUID, *, status: str, by: UUID | None, note: str | None
) -> None:
    await session.execute(
        update(Reminder)
        .where(Reminder.id == reminder_id)
        .values(status=status, decided_by=by, decided_at=datetime.now(UTC), note=note)
    )


async def set_self_paused(
    session: AsyncSession, tenant_id: UUID, engagement_id: UUID, reason: str | None
) -> None:
    await session.execute(
        pg_insert(EngagementAgentState)
        .values(tenant_id=tenant_id, engagement_id=engagement_id, self_paused_reason=reason)
        .on_conflict_do_update(
            index_elements=["tenant_id", "engagement_id"],
            set_={"self_paused_reason": reason, "updated_at": func.now()},
        )
    )
