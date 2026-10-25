"""Agents data access: agent runs and screening results only (ADR-008, ADR-103)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import ColumnElement, func, insert, select, text, update
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import QueryableAttribute, aliased

from abacus.kernel.clock import system_now
from abacus.modules.agents.models import (
    AgentActivity,
    AgentRun,
    AgentStage,
    EngagementAgentState,
    EntryAssessmentRow,
    FollowUpItem,
    FollowUpReturn,
    FollowUpSchedule,
    GuidanceDraftDecision,
    GuidanceDraftRow,
    InboxMatchProposal,
    InboxMatchRun,
    KnowledgeChunk,
    KnowledgeDocument,
    ScreeningFeedback,
    ScreeningRerunRequest,
    ScreeningResult,
    TemplateGuidanceDecision,
    TemplateGuidanceDraft,
    UploadReview,
    UploadReviewFlag,
)
from abacus.modules.identity.api import AuthContext, visible

# Engagement runs only: these reads filter on an engagement (a firm-level run's is null, and
# matches nothing).
_RUN_ENGAGEMENT = cast("QueryableAttribute[UUID]", AgentRun.engagement_id)


def _version_rows() -> ColumnElement[bool]:
    """P-06-T20 (0154): a per-run proposal on one version, never a request batch's aggregate."""
    return ScreeningResult.subject_kind == "version"


def _shown_run(run_id: QueryableAttribute[UUID]) -> ColumnElement[bool]:
    """SPEC-036 AC-5 (TASK-076): output of a run started in shadow is never shown to the firm."""
    return run_id.not_in(select(AgentRun.id).where(AgentRun.shadow.is_(True)))


async def insert_run(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: str,
    spec_version: int,
    engagement_id: UUID | None,
    evidence_version_id: UUID | None,
    initiator_user_id: UUID,
    source_event_id: UUID | None,
    task_scope: list[str],
    inbox_file_id: UUID | None = None,
    methodology_version_id: UUID | None = None,
    shadow: bool = False,
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
                inbox_file_id=inbox_file_id,
                methodology_version_id=methodology_version_id,
                shadow=shadow,
            )
            .on_conflict_do_nothing(constraint="agent_runs_once_per_event")
            .returning(AgentRun.id)
        )
    ).scalar_one_or_none()


async def runs_since(
    session: AsyncSession, agent_id: str, engagement_id: UUID | None, since: datetime
) -> int:
    """The agent's runs for the engagement since `since` (the action cap, SPEC-007); with no
    engagement, its firm-level runs (TASK-074)."""
    on = (
        AgentRun.engagement_id.is_(None)
        if engagement_id is None
        else AgentRun.engagement_id == engagement_id
    )
    count = await session.scalar(
        select(func.count())
        .select_from(AgentRun)
        .where(AgentRun.agent_id == agent_id, on, AgentRun.started_at >= since)
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
            finished_at=system_now(),
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
            select(ScreeningResult.id).where(
                ScreeningResult.agent_run_id == run_id, _version_rows()
            )
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
            .where(
                ScreeningResult.evidence_version_id == evidence_version_id,
                _version_rows(),
                _shown_run(ScreeningResult.agent_run_id),
            )
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
                    _version_rows(),
                    _shown_run(ScreeningResult.agent_run_id),
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
    paused_at = func.abacus_now() if by is not None else None
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


async def follow_up_history(
    session: AsyncSession, item_ids: Sequence[UUID]
) -> Sequence[tuple[UUID, date, int, datetime]]:
    """Each item's reminders that weren't dismissed: (item, due date then, sequence, when), for the
    agent's cadence on the engagement it serves (LIST_EXEMPT)."""
    if not item_ids:
        return []
    rows = await session.execute(
        select(
            FollowUpItem.request_item_id,
            FollowUpItem.due_on,
            FollowUpItem.sequence,
            FollowUpSchedule.created_at,
        )
        .join(FollowUpSchedule, FollowUpSchedule.id == FollowUpItem.follow_up_id)
        .where(FollowUpItem.request_item_id.in_(item_ids), FollowUpSchedule.status != "dismissed")
    )
    return [(i, d, n, at) for i, d, n, at in rows.all()]


async def drafted_item_ids(session: AsyncSession, engagement_id: UUID) -> set[UUID]:
    """TASK-104: items already in a follow-up waiting for a person (LIST_EXEMPT, as above)."""
    rows = await session.execute(
        select(FollowUpItem.request_item_id)
        .join(FollowUpSchedule, FollowUpSchedule.id == FollowUpItem.follow_up_id)
        .where(
            FollowUpSchedule.engagement_id == engagement_id, FollowUpSchedule.status == "drafted"
        )
    )
    return set(rows.scalars().all())


async def insert_follow_up(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    engagement_id: UUID,
    recipient_user_id: UUID,
    status: str,
    agent_run_id: UUID | None,
    items: Sequence[tuple[UUID, date, int]],
    kind: str = "overdue",
    drafted_by_kind: str = "agent",
    binder_id: UUID | None = None,
    recipient_contact_id: UUID | None = None,
    template_key: str | None = None,
    body_fingerprint: str | None = None,
) -> UUID:
    follow_up_id = (
        await session.execute(
            insert(FollowUpSchedule)
            .values(
                tenant_id=tenant_id,
                engagement_id=engagement_id,
                recipient_user_id=recipient_user_id,
                status=status,
                agent_run_id=agent_run_id,
                kind=kind,
                drafted_by_kind=drafted_by_kind,
                binder_id=binder_id,
                recipient_contact_id=recipient_contact_id,
                template_key=template_key,
                body_fingerprint=body_fingerprint,
            )
            .returning(FollowUpSchedule.id)
        )
    ).scalar_one()
    for item_id, due_on, sequence in items:
        await session.execute(
            insert(FollowUpItem).values(
                tenant_id=tenant_id,
                follow_up_id=follow_up_id,
                request_item_id=item_id,
                due_on=due_on,
                sequence=sequence,
            )
        )
    return follow_up_id


async def drafted_follow_ups(
    session: AsyncSession, engagement_id: UUID
) -> Sequence[tuple[FollowUpSchedule, Sequence[UUID]]]:
    """One engagement's drafts, after `authorise(follow_up.draft)` on it (LIST_EXEMPT)."""
    rows = (
        (
            await session.execute(
                select(FollowUpSchedule)
                .where(
                    FollowUpSchedule.engagement_id == engagement_id,
                    FollowUpSchedule.status == "drafted",
                )
                .order_by(FollowUpSchedule.created_at, FollowUpSchedule.id)
            )
        )
        .scalars()
        .all()
    )
    found: list[tuple[FollowUpSchedule, Sequence[UUID]]] = []
    for row in rows:
        items = (
            (
                await session.execute(
                    select(FollowUpItem.request_item_id).where(FollowUpItem.follow_up_id == row.id)
                )
            )
            .scalars()
            .all()
        )
        found.append((row, items))
    return found


async def waiting_pairs(
    session: AsyncSession, recipient_user_ids: Sequence[UUID]
) -> set[tuple[UUID, UUID]]:
    """P-06-T14: (recipient, request) already in a follow-up waiting for a person, so a new
    draft never repeats them. For a caller that authorised `follow_up.draft` on the requests'
    engagements (LIST_EXEMPT: identifiers only)."""
    if not recipient_user_ids:
        return set()
    rows = await session.execute(
        select(FollowUpSchedule.recipient_user_id, FollowUpItem.request_item_id)
        .join(FollowUpItem, FollowUpItem.follow_up_id == FollowUpSchedule.id)
        .where(
            FollowUpSchedule.recipient_user_id.in_(list(recipient_user_ids)),
            FollowUpSchedule.status == "drafted",
        )
    )
    return {(r, i) for r, i in rows.all()}


async def insert_chase_draft(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    engagement_id: UUID,
    recipient_user_id: UUID,
    items: Sequence[tuple[UUID, date, int]],
    binder_id: UUID | None,
    recipient_contact_id: UUID | None,
    template_key: str,
    body_fingerprint: str,
) -> tuple[UUID, int] | None:
    """P-06-T14: a person's chase draft for one client contact, or the requests added to the one
    already waiting for that contact (the partial unique index decides, so concurrent drafts
    never duplicate). Returns (follow-up, requests added), or None when the waiting draft was
    edited: its wording is the person's, so nothing joins it."""
    created = (
        await session.execute(
            pg_insert(FollowUpSchedule)
            .values(
                tenant_id=tenant_id,
                engagement_id=engagement_id,
                recipient_user_id=recipient_user_id,
                status="drafted",
                agent_run_id=None,
                kind="chase",
                drafted_by_kind="agent",
                binder_id=binder_id,
                recipient_contact_id=recipient_contact_id,
                template_key=template_key,
                body_fingerprint=body_fingerprint,
            )
            .on_conflict_do_nothing(
                index_elements=["tenant_id", "engagement_id", "recipient_user_id"],
                index_where=(FollowUpSchedule.status == "drafted")
                & (FollowUpSchedule.kind == "chase"),
            )
            .returning(FollowUpSchedule.id)
        )
    ).scalar_one_or_none()
    follow_up_id = created
    if follow_up_id is None:
        waiting = (
            await session.execute(
                select(FollowUpSchedule)
                .where(
                    FollowUpSchedule.engagement_id == engagement_id,
                    FollowUpSchedule.recipient_user_id == recipient_user_id,
                    FollowUpSchedule.status == "drafted",
                    FollowUpSchedule.kind == "chase",
                )
                .with_for_update()
            )
        ).scalar_one()
        if waiting.edit_fingerprint is not None:
            return None
        follow_up_id = waiting.id
    added = 0
    for item_id, due_on, sequence in items:
        inserted = (
            await session.execute(
                pg_insert(FollowUpItem)
                .values(
                    tenant_id=tenant_id,
                    follow_up_id=follow_up_id,
                    request_item_id=item_id,
                    due_on=due_on,
                    sequence=sequence,
                )
                .on_conflict_do_nothing()
                .returning(FollowUpItem.request_item_id)
            )
        ).scalar_one_or_none()
        added += inserted is not None
    return follow_up_id, added


async def get_follow_up(
    session: AsyncSession, follow_up_id: UUID, *, lock: bool = False
) -> FollowUpSchedule | None:
    query = select(FollowUpSchedule).where(FollowUpSchedule.id == follow_up_id)
    if lock:
        query = query.with_for_update()
    return (await session.execute(query)).scalar_one_or_none()


async def follow_up_item_rows(session: AsyncSession, follow_up_id: UUID) -> Sequence[FollowUpItem]:
    """One follow-up's items, for a caller that authorised the follow-up (LIST_EXEMPT)."""
    return (
        (
            await session.execute(
                select(FollowUpItem)
                .where(FollowUpItem.follow_up_id == follow_up_id)
                .order_by(FollowUpItem.due_on, FollowUpItem.request_item_id)
            )
        )
        .scalars()
        .all()
    )


async def set_follow_up(
    session: AsyncSession, follow_up_id: UUID, values: dict[str, object]
) -> None:
    await session.execute(
        update(FollowUpSchedule).where(FollowUpSchedule.id == follow_up_id).values(**values)
    )


async def insert_follow_up_returns(
    session: AsyncSession,
    tenant_id: UUID,
    follow_up_id: UUID,
    returns: Sequence[tuple[UUID, str]],
) -> None:
    for version_id, reason in returns:
        await session.execute(
            insert(FollowUpReturn).values(
                tenant_id=tenant_id,
                follow_up_id=follow_up_id,
                evidence_version_id=version_id,
                reason_code=reason,
            )
        )


async def set_self_paused(
    session: AsyncSession, tenant_id: UUID, engagement_id: UUID, reason: str | None
) -> None:
    # The app role may INSERT only the columns a person's pause sets (migration 0039) and UPDATE
    # `self_paused_reason` (0040): make the row, then update it, so the INSERT names no other.
    await session.execute(
        pg_insert(EngagementAgentState)
        .values(tenant_id=tenant_id, engagement_id=engagement_id)
        .on_conflict_do_nothing(index_elements=["tenant_id", "engagement_id"])
    )
    await session.execute(
        update(EngagementAgentState)
        .where(
            EngagementAgentState.tenant_id == tenant_id,
            EngagementAgentState.engagement_id == engagement_id,
        )
        .values(self_paused_reason=reason, updated_at=func.now())
    )


# --- The upload reviewer (SPEC-030; TASK-058) ----------------------------------------------------


async def insert_upload_review(session: AsyncSession, *, values: dict[str, object]) -> UUID:
    review_id = uuid4()
    await session.execute(insert(UploadReview).values(id=review_id, **values))
    return review_id


async def insert_review_flags(session: AsyncSession, rows: list[dict[str, object]]) -> None:
    if rows:
        await session.execute(insert(UploadReviewFlag).values(rows))


async def insert_inbox_match(session: AsyncSession, *, values: dict[str, object]) -> UUID:
    """SPEC-033 (TASK-065): a matcher run's result; its proposals follow."""
    match_id = uuid4()
    await session.execute(insert(InboxMatchRun).values(id=match_id, **values))
    return match_id


async def insert_match_proposals(session: AsyncSession, rows: list[dict[str, object]]) -> None:
    if rows:
        await session.execute(insert(InboxMatchProposal).values(rows))


async def insert_guidance_draft(session: AsyncSession, **values: object) -> None:
    """SPEC-035 (TASK-072): a drafter run's draft."""
    await session.execute(insert(GuidanceDraftRow).values(**values))


async def review_for_run(session: AsyncSession, run_id: UUID) -> UploadReview | None:
    """The review an upload reviewer run recorded (the caller authorised on its engagement)."""
    return (
        await session.execute(select(UploadReview).where(UploadReview.agent_run_id == run_id))
    ).scalar_one_or_none()


async def latest_review_run(
    session: AsyncSession, ctx: AuthContext, agent_id: str, version_id: UUID
) -> AgentRun | None:
    """SPEC-030 (TASK-059): the newest upload reviewer run on a version the caller may read."""
    return (
        await session.execute(
            select(AgentRun)
            .where(
                AgentRun.agent_id == agent_id,
                AgentRun.evidence_version_id == version_id,
                AgentRun.shadow.is_(False),
                visible(ctx, "upload_review.read", _RUN_ENGAGEMENT),
            )
            .order_by(AgentRun.started_at.desc(), AgentRun.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def shown_flags(
    session: AsyncSession, ctx: AuthContext, run_id: UUID
) -> list[UploadReviewFlag]:
    """A run's shown flags, in order (hidden ones stay for evaluation and audit)."""
    return list(
        (
            await session.execute(
                select(UploadReviewFlag)
                .join(
                    UploadReview,
                    (UploadReview.id == UploadReviewFlag.review_id)
                    & (UploadReview.tenant_id == UploadReviewFlag.tenant_id),
                )
                .where(
                    UploadReview.agent_run_id == run_id,
                    UploadReviewFlag.shown.is_(True),
                    _shown_run(UploadReview.agent_run_id),
                    visible(ctx, "upload_review.read", UploadReview.engagement_id),
                )
                .order_by(UploadReviewFlag.position)
            )
        )
        .scalars()
        .all()
    )


async def shown_flag_counts(
    session: AsyncSession, ctx: AuthContext, engagement_id: UUID
) -> dict[UUID, int]:
    """Per evidence version of the engagement, the shown flags of its latest review."""
    rows = (
        await session.execute(
            select(
                UploadReview.evidence_version_id,
                UploadReview.created_at,
                UploadReview.id,
                UploadReviewFlag.shown,
            )
            .outerjoin(
                UploadReviewFlag,
                (UploadReviewFlag.review_id == UploadReview.id)
                & (UploadReviewFlag.tenant_id == UploadReview.tenant_id),
            )
            .where(
                UploadReview.engagement_id == engagement_id,
                visible(ctx, "upload_review.read", UploadReview.engagement_id),
                _shown_run(UploadReview.agent_run_id),
            )
        )
    ).all()
    newest: dict[UUID, tuple[datetime, UUID]] = {}
    for row in rows:
        seen = newest.get(row.evidence_version_id)
        if seen is None or (row.created_at, row.id) > seen:
            newest[row.evidence_version_id] = (row.created_at, row.id)
    counts: dict[UUID, int] = {}
    for row in rows:
        if newest[row.evidence_version_id][1] == row.id and row.shown:
            counts[row.evidence_version_id] = counts.get(row.evidence_version_id, 0) + 1
    return counts


# --- The matcher's reads (SPEC-033; TASK-066) ---------------------------------------------------


async def latest_match_runs(
    session: AsyncSession, ctx: AuthContext, agent_id: str, engagement_id: UUID
) -> list[AgentRun]:
    """The newest matcher run per inbox file of an engagement the caller may read matches on."""
    return list(
        (
            await session.execute(
                select(AgentRun)
                .where(
                    AgentRun.agent_id == agent_id,
                    AgentRun.engagement_id == engagement_id,
                    AgentRun.inbox_file_id.is_not(None),
                    AgentRun.shadow.is_(False),
                    visible(ctx, "inbox_match.read", _RUN_ENGAGEMENT),
                )
                .ext(distinct_on(AgentRun.inbox_file_id))
                .order_by(AgentRun.inbox_file_id, AgentRun.started_at.desc(), AgentRun.id.desc())
            )
        )
        .scalars()
        .all()
    )


async def list_match_results(
    session: AsyncSession, ctx: AuthContext, run_ids: Sequence[UUID]
) -> list[tuple[InboxMatchRun, InboxMatchProposal | None]]:
    """Those runs' results with their shown proposals in rank order (hidden ones stay for
    evaluation and audit)."""
    if not run_ids:
        return []
    rows = await session.execute(
        select(InboxMatchRun, InboxMatchProposal)
        .outerjoin(
            InboxMatchProposal,
            (InboxMatchProposal.match_id == InboxMatchRun.id)
            & (InboxMatchProposal.tenant_id == InboxMatchRun.tenant_id)
            & InboxMatchProposal.shown.is_(True),
        )
        .where(
            InboxMatchRun.agent_run_id.in_(run_ids),
            visible(ctx, "inbox_match.read", InboxMatchRun.engagement_id),
            _shown_run(InboxMatchRun.agent_run_id),
        )
        .order_by(InboxMatchRun.agent_run_id, InboxMatchProposal.rank)
    )
    return list(rows.tuples().all())


async def shown_picks(
    session: AsyncSession, inbox_file_ids: Sequence[UUID]
) -> dict[UUID, list[tuple[UUID, Decimal]]]:
    """SPEC-033 (TASK-066 D1): per file, the latest completed matcher result's shown requests,
    best first; for evidence's inbox listing, which already authorised the caller on these files
    (request IDs only, never the matcher's words). LIST_EXEMPT."""
    if not inbox_file_ids:
        return {}
    latest = (
        select(InboxMatchRun.id)
        .where(
            InboxMatchRun.inbox_file_id.in_(inbox_file_ids),
            _shown_run(InboxMatchRun.agent_run_id),
        )
        .ext(distinct_on(InboxMatchRun.inbox_file_id))
        .order_by(InboxMatchRun.inbox_file_id, InboxMatchRun.created_at.desc())
        .subquery()
    )
    rows = await session.execute(
        select(
            InboxMatchRun.inbox_file_id,
            InboxMatchProposal.request_item_id,
            InboxMatchProposal.confidence,
        )
        .join(InboxMatchProposal, InboxMatchProposal.match_id == InboxMatchRun.id)
        .where(InboxMatchRun.id.in_(select(latest.c.id)), InboxMatchProposal.shown.is_(True))
        .order_by(InboxMatchRun.inbox_file_id, InboxMatchProposal.rank)
    )
    found: dict[UUID, list[tuple[UUID, Decimal]]] = {}
    for file_id, item_id, confidence in rows.tuples().all():
        found.setdefault(file_id, []).append((item_id, confidence))
    return found


# --- Guidance drafts in the product (SPEC-035; TASK-073) ----------------------------------------


async def pending_guidance_drafts(
    session: AsyncSession, ctx: AuthContext, engagement_id: UUID
) -> list[GuidanceDraftRow]:
    """Per item, its newest draft that passed code's checks and has no decision yet."""
    decided = select(GuidanceDraftDecision.draft_id)
    return list(
        (
            await session.execute(
                select(GuidanceDraftRow)
                .where(
                    GuidanceDraftRow.engagement_id == engagement_id,
                    GuidanceDraftRow.passed_checks.is_(True),
                    GuidanceDraftRow.id.not_in(decided),
                    _shown_run(GuidanceDraftRow.agent_run_id),
                    visible(ctx, "guidance_draft.read", GuidanceDraftRow.engagement_id),
                )
                .ext(distinct_on(GuidanceDraftRow.request_item_id))
                .order_by(GuidanceDraftRow.request_item_id, GuidanceDraftRow.created_at.desc())
            )
        )
        .scalars()
        .all()
    )


async def get_guidance_draft(session: AsyncSession, draft_id: UUID) -> GuidanceDraftRow | None:
    return (
        await session.execute(select(GuidanceDraftRow).where(GuidanceDraftRow.id == draft_id))
    ).scalar_one_or_none()


async def insert_draft_decision(session: AsyncSession, **values: object) -> bool:
    """False when the draft already has a decision."""
    made = await session.execute(
        pg_insert(GuidanceDraftDecision)
        .values(**values)
        .on_conflict_do_nothing()
        .returning(GuidanceDraftDecision.draft_id)
    )
    return made.scalar_one_or_none() is not None


# --- Drafted guidance on templates (SPEC-035 Q3; TASK-074) -------------------------------------


async def insert_template_draft(session: AsyncSession, **values: object) -> None:
    await session.execute(insert(TemplateGuidanceDraft).values(**values))


async def template_drafts(
    session: AsyncSession, version_id: UUID
) -> list[tuple[TemplateGuidanceDraft, TemplateGuidanceDecision | None]]:
    """Per template item, its newest draft that passed code's checks, with its decision if any.
    Firm-level, after `authorise(template_guidance.read)` on the firm (LIST_EXEMPT)."""
    newest = (
        select(TemplateGuidanceDraft)
        .where(
            TemplateGuidanceDraft.methodology_version_id == version_id,
            TemplateGuidanceDraft.passed_checks.is_(True),
            _shown_run(TemplateGuidanceDraft.agent_run_id),
        )
        .ext(distinct_on(TemplateGuidanceDraft.position))
        .order_by(TemplateGuidanceDraft.position, TemplateGuidanceDraft.created_at.desc())
        .subquery()
    )
    draft = aliased(TemplateGuidanceDraft, newest)
    rows = await session.execute(
        select(draft, TemplateGuidanceDecision)
        .outerjoin(TemplateGuidanceDecision, TemplateGuidanceDecision.draft_id == draft.id)
        .order_by(draft.position)
    )
    return [(d, c) for d, c in rows.tuples().all()]


async def get_template_draft(
    session: AsyncSession, draft_id: UUID
) -> TemplateGuidanceDraft | None:
    return (
        await session.execute(
            select(TemplateGuidanceDraft).where(TemplateGuidanceDraft.id == draft_id)
        )
    ).scalar_one_or_none()


async def insert_template_decision(session: AsyncSession, **values: object) -> bool:
    """False when the draft already has a decision."""
    made = await session.execute(
        pg_insert(TemplateGuidanceDecision)
        .values(**values)
        .on_conflict_do_nothing()
        .returning(TemplateGuidanceDecision.draft_id)
    )
    return made.scalar_one_or_none() is not None


# --- Stages (SPEC-036; TASK-076) ----------------------------------------------------------------


async def stage_of(session: AsyncSession, agent_id: str) -> str | None:
    """The agent's newest stage row for the session's firm, or None."""
    return await session.scalar(
        select(AgentStage.stage)
        .where(AgentStage.agent_id == agent_id)
        .order_by(AgentStage.created_at.desc())
        .limit(1)
    )


# --- The entry assessor (SPEC-037 Q4; TASK-085) -------------------------------------------------


async def insert_entry_assessment(session: AsyncSession, **values: object) -> None:
    await session.execute(insert(EntryAssessmentRow).values(**values))


async def newest_assessments(
    session: AsyncSession, ctx: AuthContext, engagement_id: UUID, item_ids: Sequence[UUID]
) -> list[EntryAssessmentRow]:
    """Per entry, its newest assessment from a run that wasn't in shadow (SPEC-036)."""
    if not item_ids:
        return []
    return list(
        (
            await session.execute(
                select(EntryAssessmentRow)
                .where(
                    EntryAssessmentRow.engagement_id == engagement_id,
                    EntryAssessmentRow.selected_item_id.in_(item_ids),
                    visible(ctx, "procedure.read", EntryAssessmentRow.engagement_id),
                    _shown_run(EntryAssessmentRow.agent_run_id),
                )
                .ext(distinct_on(EntryAssessmentRow.selected_item_id))
                .order_by(
                    EntryAssessmentRow.selected_item_id, EntryAssessmentRow.created_at.desc()
                )
            )
        )
        .scalars()
        .all()
    )


async def engagement_runs(
    session: AsyncSession, ctx: AuthContext, engagement_id: UUID, limit: int
) -> Sequence[AgentRun]:
    """TASK-461: the engagement's runs, newest first, through `visible()`; shadow runs never."""
    return (
        (
            await session.execute(
                select(AgentRun)
                .where(
                    AgentRun.engagement_id == engagement_id,
                    AgentRun.shadow.is_(False),
                    visible(ctx, "agent_run.read", _RUN_ENGAGEMENT),
                )
                .order_by(AgentRun.started_at.desc(), AgentRun.id.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )


async def screening_results_of_run(
    session: AsyncSession, run_id: UUID
) -> Sequence[ScreeningResult]:
    """LIST_EXEMPT: one run's results, after authorising on its engagement."""
    return (
        (
            await session.execute(
                select(ScreeningResult).where(
                    ScreeningResult.agent_run_id == run_id, _version_rows()
                )
            )
        )
        .scalars()
        .all()
    )


# --- The screening aggregate (P-06-T20; DEC-48, DEC-324) -----------------------------------------
# The composer reads in a system context, keyed by the item's live versions; the card's reads
# follow `authorise(upload_review.read)` on the engagement and apply `visible()` to the head.


def _batch_rows() -> ColumnElement[bool]:
    return ScreeningResult.subject_kind == "request_batch"


@dataclass(frozen=True)
class ReviewRunFacts:
    """An upload reviewer run on a version and, when it completed, its review."""

    run_id: UUID
    evidence_version_id: UUID
    status: str
    started_at: datetime
    finished_at: datetime | None
    review_id: UUID | None
    prompt_ref: str | None


async def review_runs_of_versions(
    session: AsyncSession, agent_id: str, version_ids: Sequence[UUID]
) -> list[ReviewRunFacts]:
    """LIST_EXEMPT: every non-shadow run of the reviewer on these versions (the composer's and
    the card's, after authorising on their engagement), oldest first."""
    if not version_ids:
        return []
    rows = await session.execute(
        select(
            AgentRun.id,
            AgentRun.evidence_version_id,
            AgentRun.status,
            AgentRun.started_at,
            AgentRun.finished_at,
            UploadReview.id.label("review_id"),
            UploadReview.prompt_ref,
        )
        .outerjoin(
            UploadReview,
            (UploadReview.agent_run_id == AgentRun.id)
            & (UploadReview.tenant_id == AgentRun.tenant_id),
        )
        .where(
            AgentRun.agent_id == agent_id,
            AgentRun.evidence_version_id.in_(list(version_ids)),
            AgentRun.shadow.is_(False),
        )
        .order_by(AgentRun.started_at, AgentRun.id)
    )
    return [
        ReviewRunFacts(
            r.id,
            cast(UUID, r.evidence_version_id),
            r.status,
            r.started_at,
            r.finished_at,
            r.review_id,
            r.prompt_ref,
        )
        for r in rows.all()
    ]


async def shown_flags_of_reviews(
    session: AsyncSession, review_ids: Sequence[UUID]
) -> list[tuple[UUID, int, str]]:
    """LIST_EXEMPT: the shown flags (review, position, category) of reviews the composer chose.
    Shown means a code-verified quote and enough confidence (SPEC-030 Q3; INV-2)."""
    if not review_ids:
        return []
    rows = await session.execute(
        select(UploadReviewFlag.review_id, UploadReviewFlag.position, UploadReviewFlag.category)
        .where(UploadReviewFlag.review_id.in_(list(review_ids)), UploadReviewFlag.shown.is_(True))
        .order_by(UploadReviewFlag.review_id, UploadReviewFlag.position)
    )
    return [(r.review_id, r.position, r.category) for r in rows.all()]


async def version_results_of(
    session: AsyncSession, version_ids: Sequence[UUID]
) -> dict[UUID, UUID]:
    """LIST_EXEMPT: the newest shown per-version screening result of each version."""
    if not version_ids:
        return {}
    rows = await session.execute(
        select(ScreeningResult.evidence_version_id, ScreeningResult.id)
        .where(
            ScreeningResult.evidence_version_id.in_(list(version_ids)),
            _version_rows(),
            _shown_run(ScreeningResult.agent_run_id),
        )
        .ext(distinct_on(ScreeningResult.evidence_version_id))
        .order_by(
            ScreeningResult.evidence_version_id,
            ScreeningResult.created_at.desc(),
            ScreeningResult.id.desc(),
        )
    )
    return {r.evidence_version_id: r.id for r in rows.all()}


async def aggregate_head(session: AsyncSession, item_id: UUID) -> ScreeningResult | None:
    """The item's newest aggregate (the head of its chain), for the system composer."""
    return (
        await session.execute(
            select(ScreeningResult)
            .where(ScreeningResult.request_item_id == item_id, _batch_rows())
            .order_by(ScreeningResult.batch_no.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def aggregate_head_for(
    session: AsyncSession, ctx: AuthContext, item_id: UUID
) -> ScreeningResult | None:
    """The item's newest aggregate, if the caller may read its engagement's reviews."""
    return (
        await session.execute(
            select(ScreeningResult)
            .where(
                ScreeningResult.request_item_id == item_id,
                _batch_rows(),
                visible(ctx, "upload_review.read", ScreeningResult.engagement_id),
            )
            .order_by(ScreeningResult.batch_no.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def aggregate_for(
    session: AsyncSession, ctx: AuthContext, result_id: UUID
) -> ScreeningResult | None:
    """One aggregate by id, if the caller may read its engagement's reviews (else None: 404)."""
    return (
        await session.execute(
            select(ScreeningResult).where(
                ScreeningResult.id == result_id,
                _batch_rows(),
                visible(ctx, "upload_review.read", ScreeningResult.engagement_id),
            )
        )
    ).scalar_one_or_none()


async def insert_aggregate(session: AsyncSession, *, values: dict[str, object]) -> UUID:
    result_id = uuid4()
    await session.execute(
        insert(ScreeningResult).values(id=result_id, subject_kind="request_batch", **values)
    )
    return result_id


async def insert_feedback(session: AsyncSession, *, values: dict[str, object]) -> None:
    await session.execute(insert(ScreeningFeedback).values(**values))


async def latest_feedback(
    session: AsyncSession, result_id: UUID, user_id: UUID
) -> ScreeningFeedback | None:
    """The person's newest feedback on one aggregate (their own row)."""
    return (
        await session.execute(
            select(ScreeningFeedback)
            .where(
                ScreeningFeedback.screening_result_id == result_id,
                ScreeningFeedback.user_id == user_id,
            )
            .order_by(ScreeningFeedback.created_at.desc(), ScreeningFeedback.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def items_screened_with(session: AsyncSession, version_id: UUID) -> list[UUID]:
    """LIST_EXEMPT: the items whose aggregates composed this version (a withdrawal recomposes
    them; the system composer's read)."""
    rows = await session.execute(
        select(ScreeningResult.request_item_id)
        .where(
            _batch_rows(),
            func.array_position(ScreeningResult.evidence_version_ids, version_id).is_not(None),
        )
        .distinct()
    )
    return [cast(UUID, r) for r in rows.scalars().all()]


async def lock_item_rerun(session: AsyncSession, item_id: UUID) -> None:
    """Serialise reruns of one item until this transaction ends (the running check, the rate
    limit and the dispatch happen under it)."""
    key = func.hashtextextended(f"screening_rerun:{item_id}", 0)
    await session.execute(select(func.pg_advisory_xact_lock(key)))


async def rerun_since(session: AsyncSession, item_id: UUID, seconds: int) -> bool:
    """Whether a person asked for a rerun of the item in the last `seconds` (system time)."""
    found = await session.execute(
        select(ScreeningRerunRequest.id)
        .where(
            ScreeningRerunRequest.request_item_id == item_id,
            ScreeningRerunRequest.created_at
            > func.clock_timestamp() - func.make_interval(0, 0, 0, 0, 0, 0, seconds),
        )
        .limit(1)
    )
    return found.scalar_one_or_none() is not None


async def insert_rerun(session: AsyncSession, *, values: dict[str, object]) -> None:
    await session.execute(insert(ScreeningRerunRequest).values(**values))


# --- P-04-T16: the proposals that may wait on a person (C13 gate sources) ----------------------
# LIST_EXEMPT: the system projector's reads, per engagement or (rebuild) for the whole firm; the
# list route filters the projection through `visible()`.


async def latest_screenings_for_gates(
    session: AsyncSession, engagement_id: UUID | None
) -> Sequence[tuple[UUID, UUID, UUID]]:
    """(result, engagement, version): the newest shown result of each version."""
    stmt = select(
        ScreeningResult.id, ScreeningResult.engagement_id, ScreeningResult.evidence_version_id
    ).where(_shown_run(ScreeningResult.agent_run_id))
    if engagement_id is not None:
        stmt = stmt.where(ScreeningResult.engagement_id == engagement_id)
    rows = await session.execute(
        stmt.ext(distinct_on(ScreeningResult.evidence_version_id)).order_by(
            ScreeningResult.evidence_version_id,
            ScreeningResult.created_at.desc(),
            ScreeningResult.id.desc(),
        )
    )
    return [(r[0], r[1], r[2]) for r in rows.all()]


async def latest_upload_reviews_for_gates(
    session: AsyncSession, engagement_id: UUID | None
) -> Sequence[tuple[UUID, UUID, UUID]]:
    """(review, engagement, version): the newest shown review of each version, when it raised
    a concern (a review with none asks nothing of anyone)."""
    latest = select(
        UploadReview.id,
        UploadReview.engagement_id,
        UploadReview.evidence_version_id,
        UploadReview.no_concerns,
    ).where(_shown_run(UploadReview.agent_run_id))
    if engagement_id is not None:
        latest = latest.where(UploadReview.engagement_id == engagement_id)
    rows = await session.execute(
        latest.ext(distinct_on(UploadReview.evidence_version_id)).order_by(
            UploadReview.evidence_version_id,
            UploadReview.created_at.desc(),
            UploadReview.id.desc(),
        )
    )
    return [(r[0], r[1], r[2]) for r in rows.all() if not r[3]]


async def latest_matches_for_gates(
    session: AsyncSession, engagement_id: UUID | None
) -> Sequence[tuple[UUID, UUID, UUID]]:
    """(match run, engagement, inbox file): the newest shown run of each file, when it showed a
    proposal."""
    stmt = select(
        InboxMatchRun.id, InboxMatchRun.engagement_id, InboxMatchRun.inbox_file_id
    ).where(_shown_run(InboxMatchRun.agent_run_id))
    if engagement_id is not None:
        stmt = stmt.where(InboxMatchRun.engagement_id == engagement_id)
    rows = (
        await session.execute(
            stmt.ext(distinct_on(InboxMatchRun.inbox_file_id)).order_by(
                InboxMatchRun.inbox_file_id,
                InboxMatchRun.created_at.desc(),
                InboxMatchRun.id.desc(),
            )
        )
    ).all()
    if not rows:
        return []
    shown = set(
        (
            await session.execute(
                select(InboxMatchProposal.match_id).where(
                    InboxMatchProposal.match_id.in_([r[0] for r in rows]),
                    InboxMatchProposal.shown.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    return [(r[0], r[1], r[2]) for r in rows if r[0] in shown]


async def undecided_drafts_for_gates(
    session: AsyncSession, engagement_id: UUID | None
) -> Sequence[tuple[UUID, UUID, UUID]]:
    """(draft, engagement, request item): the newest shown draft of each item that passed the
    checks and that no person has decided."""
    stmt = select(
        GuidanceDraftRow.id,
        GuidanceDraftRow.engagement_id,
        GuidanceDraftRow.request_item_id,
        GuidanceDraftRow.passed_checks,
    ).where(_shown_run(GuidanceDraftRow.agent_run_id))
    if engagement_id is not None:
        stmt = stmt.where(GuidanceDraftRow.engagement_id == engagement_id)
    rows = (
        await session.execute(
            stmt.ext(distinct_on(GuidanceDraftRow.request_item_id)).order_by(
                GuidanceDraftRow.request_item_id,
                GuidanceDraftRow.created_at.desc(),
                GuidanceDraftRow.id.desc(),
            )
        )
    ).all()
    candidates = [r for r in rows if r[3]]
    if not candidates:
        return []
    decided = set(
        (
            await session.execute(
                select(GuidanceDraftDecision.draft_id).where(
                    GuidanceDraftDecision.draft_id.in_([r[0] for r in candidates])
                )
            )
        )
        .scalars()
        .all()
    )
    return [(r[0], r[1], r[2]) for r in candidates if r[0] not in decided]


@dataclass(frozen=True)
class RunWriteRow:
    """A suggestion or proposal the run made (migration 0095), with its newest decision."""

    kind: str  # suggestion | proposal
    id: UUID
    target_type: str | None
    target_id: UUID | None
    key: str  # the suggestion's field key, or the proposal's kind
    state: str
    at: datetime
    decision: str | None
    decided_by: UUID | None
    decided_at: datetime | None


async def run_writes(session: AsyncSession, run_id: UUID) -> list[RunWriteRow]:
    """LIST_EXEMPT: one run's suggestions and proposals, after authorising on its engagement."""
    found = await session.execute(
        text(
            """
            SELECT 'suggestion' AS kind, s.id, s.target_type, s.target_id, s.field_key AS key,
                   s.status AS state, s.created_at AS at,
                   d.decision, d.decided_by, d.created_at AS decided_at
              FROM suggestions s
              LEFT JOIN LATERAL (
                SELECT decision, decided_by, created_at FROM suggestion_decisions
                 WHERE suggestion_id = s.id ORDER BY created_at DESC, id DESC LIMIT 1
              ) d ON true
             WHERE s.agent_run_id = :run
            UNION ALL
            SELECT 'proposal', p.id, NULL, NULL, p.kind, p.state, p.created_at,
                   d.decision, d.decided_by, d.created_at
              FROM proposals p
              LEFT JOIN LATERAL (
                SELECT decision, decided_by, created_at FROM proposal_decisions
                 WHERE proposal_id = p.id ORDER BY created_at DESC, id DESC LIMIT 1
              ) d ON true
             WHERE p.agent_run_id = :run
             ORDER BY at, id
            """
        ),
        {"run": run_id},
    )
    return [RunWriteRow(*row) for row in found.all()]
