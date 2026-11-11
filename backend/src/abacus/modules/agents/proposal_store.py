"""Reads and writes of suggestions and proposals (P-04-T24; migration 0095, 0230).

Every read here is by id, for a caller that authorised on the row's engagement (LIST_EXEMPT: no
list query). Writes run in the caller's unit of work; the database binds each decision row to the
transaction's actor and holds the state transitions (0230).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast
from uuid import UUID

from sqlalchemy import func, insert, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.modules.agents.models import (
    AgentRun,
    InboxMatchDecision,
    InboxMatchProposal,
    InboxMatchRun,
    Proposal,
    ProposalDecision,
    ProposalRow,
    ScreeningResult,
    Suggestion,
    SuggestionDecision,
    UploadReview,
    UploadReviewFlag,
)
from abacus.modules.agents.repository import shown_run


async def get_proposal(session: AsyncSession, proposal_id: UUID) -> Proposal | None:
    return await session.get(Proposal, proposal_id)


async def lock_proposal(session: AsyncSession, proposal_id: UUID) -> Proposal | None:
    found = await session.execute(
        select(Proposal).where(Proposal.id == proposal_id).with_for_update()
    )
    return found.scalar_one_or_none()


async def rows_of(session: AsyncSession, proposal_id: UUID) -> Sequence[ProposalRow]:
    found = await session.execute(
        select(ProposalRow).where(ProposalRow.proposal_id == proposal_id).order_by(ProposalRow.n)
    )
    return found.scalars().all()


async def latest_decision(session: AsyncSession, proposal_id: UUID) -> ProposalDecision | None:
    found = await session.execute(
        select(ProposalDecision)
        .where(ProposalDecision.proposal_id == proposal_id)
        .order_by(ProposalDecision.created_at.desc(), ProposalDecision.id.desc())
        .limit(1)
    )
    return found.scalar_one_or_none()


async def run_of(session: AsyncSession, run_id: UUID) -> AgentRun | None:
    return await session.get(AgentRun, run_id)


async def insert_proposal(session: AsyncSession, values: dict[str, object]) -> UUID:
    found = await session.execute(insert(Proposal).values(values).returning(Proposal.id))
    return found.scalar_one()


async def insert_proposal_row(session: AsyncSession, values: dict[str, object]) -> None:
    await session.execute(insert(ProposalRow).values(values))


async def insert_proposal_decision(session: AsyncSession, values: dict[str, object]) -> None:
    await session.execute(insert(ProposalDecision).values(values))


async def set_proposal(
    session: AsyncSession,
    proposal_id: UUID,
    *,
    state: str | None = None,
    routed_to_user_id: UUID | None = None,
) -> int:
    """The next version, with the new state or approver (only after their decision row)."""
    values: dict[str, object] = {"version": Proposal.version + 1}
    if state is not None:
        values["state"] = state
    if routed_to_user_id is not None:
        values["routed_to_user_id"] = routed_to_user_id
    found = await session.execute(
        update(Proposal)
        .where(Proposal.id == proposal_id)
        .values(values)
        .returning(Proposal.version)
    )
    return found.scalar_one()


async def pending_field_suggestions(
    session: AsyncSession, engagement_id: UUID, target_type: str, field_key: str
) -> Sequence[Suggestion]:
    """LIST_EXEMPT: one engagement's pending suggestions on one field of a target kind, after the
    caller authorised on the engagement. One that a proposal carries is resolved with it."""
    return (
        (
            await session.execute(
                select(Suggestion)
                .where(
                    Suggestion.engagement_id == engagement_id,
                    Suggestion.target_type == target_type,
                    Suggestion.field_key == field_key,
                    Suggestion.status == "pending",
                    Suggestion.proposal_id.is_(None),
                )
                .order_by(Suggestion.created_at, Suggestion.id)
            )
        )
        .scalars()
        .all()
    )


async def get_suggestion(session: AsyncSession, suggestion_id: UUID) -> Suggestion | None:
    return await session.get(Suggestion, suggestion_id)


async def lock_suggestion(session: AsyncSession, suggestion_id: UUID) -> Suggestion | None:
    found = await session.execute(
        select(Suggestion).where(Suggestion.id == suggestion_id).with_for_update()
    )
    return found.scalar_one_or_none()


async def lock_suggestions(
    session: AsyncSession, suggestion_ids: Sequence[UUID]
) -> dict[UUID, Suggestion]:
    if not suggestion_ids:
        return {}
    found = await session.execute(
        select(Suggestion)
        .where(Suggestion.id.in_(list(suggestion_ids)))
        .order_by(Suggestion.id)
        .with_for_update()
    )
    return {s.id: s for s in found.scalars().all()}


async def insert_suggestion(session: AsyncSession, values: dict[str, object]) -> UUID:
    found = await session.execute(insert(Suggestion).values(values).returning(Suggestion.id))
    return found.scalar_one()


async def insert_suggestion_decision(session: AsyncSession, values: dict[str, object]) -> None:
    await session.execute(insert(SuggestionDecision).values(values))


async def set_suggestion(session: AsyncSession, suggestion_id: UUID, status: str) -> int:
    found = await session.execute(
        update(Suggestion)
        .where(Suggestion.id == suggestion_id)
        .values(status=status, version=Suggestion.version + 1)
        .returning(Suggestion.version)
    )
    return found.scalar_one()


async def latest_suggestion_decision(
    session: AsyncSession, suggestion_id: UUID
) -> SuggestionDecision | None:
    found = await session.execute(
        select(SuggestionDecision)
        .where(SuggestionDecision.suggestion_id == suggestion_id)
        .order_by(SuggestionDecision.created_at.desc(), SuggestionDecision.id.desc())
        .limit(1)
    )
    return found.scalar_one_or_none()


async def run_output_text(session: AsyncSession, run_id: UUID, key: str) -> str | None:
    """A string the run recorded in its output under `key` (agent text, sanitised when the run
    finished: ADR-065), or None."""
    found = await session.execute(
        select(func.jsonb_extract_path_text(AgentRun.output, key)).where(AgentRun.id == run_id)
    )
    return found.scalar_one_or_none()


# --- P-04-T25: the typed tables the adapters project (ADR-161 clause 3) -------------------------


async def screening_result(session: AsyncSession, result_id: UUID) -> ScreeningResult | None:
    found = await session.execute(
        select(ScreeningResult).where(
            ScreeningResult.id == result_id, ScreeningResult.subject_kind == "version"
        )
    )
    return found.scalar_one_or_none()


async def upload_review_with_flags(
    session: AsyncSession, review_id: UUID
) -> tuple[UploadReview, Sequence[UploadReviewFlag]] | None:
    review = await session.get(UploadReview, review_id)
    if review is None:
        return None
    flags = await session.execute(
        select(UploadReviewFlag)
        .where(UploadReviewFlag.review_id == review_id, UploadReviewFlag.shown.is_(True))
        .order_by(UploadReviewFlag.position)
    )
    return review, flags.scalars().all()


async def newest_upload_review(session: AsyncSession, version_id: UUID) -> UUID | None:
    found = await session.execute(
        select(UploadReview.id)
        .where(
            UploadReview.evidence_version_id == version_id,
            shown_run(UploadReview.agent_run_id),  # a shadow run never supersedes (review M5)
        )
        .order_by(UploadReview.created_at.desc(), UploadReview.id.desc())
        .limit(1)
    )
    return found.scalar_one_or_none()


async def match_with_proposals(
    session: AsyncSession, match_id: UUID
) -> tuple[InboxMatchRun, Sequence[InboxMatchProposal]] | None:
    run = await session.get(InboxMatchRun, match_id)
    if run is None:
        return None
    shown = await session.execute(
        select(InboxMatchProposal)
        .where(InboxMatchProposal.match_id == match_id, InboxMatchProposal.shown.is_(True))
        .order_by(InboxMatchProposal.rank)
    )
    return run, shown.scalars().all()


async def newest_match(session: AsyncSession, inbox_file_id: UUID) -> UUID | None:
    found = await session.execute(
        select(InboxMatchRun.id)
        .where(
            InboxMatchRun.inbox_file_id == inbox_file_id,
            shown_run(InboxMatchRun.agent_run_id),  # a shadow run never supersedes (review M5)
        )
        .order_by(InboxMatchRun.created_at.desc(), InboxMatchRun.id.desc())
        .limit(1)
    )
    return found.scalar_one_or_none()


async def match_decision(session: AsyncSession, match_id: UUID) -> InboxMatchDecision | None:
    found = await session.execute(
        select(InboxMatchDecision).where(InboxMatchDecision.match_id == match_id)
    )
    return found.scalar_one_or_none()


async def insert_match_decision(session: AsyncSession, values: dict[str, object]) -> None:
    await session.execute(insert(InboxMatchDecision).values(values))


async def approver_of(session: AsyncSession, proposal_id: UUID) -> UUID | None:
    """T-04-T36: the person whose newest decision approved the proposal (an applier's subject)."""
    found = await session.scalar(
        text(
            "SELECT decided_by FROM proposal_decisions WHERE proposal_id = :p "
            "AND decision IN ('approved', 'approved_with_edits') AND undoes_decision_id IS NULL "
            "ORDER BY created_at DESC LIMIT 1"
        ),
        {"p": proposal_id},
    )
    return cast(UUID | None, found)


async def approved_rows(
    session: AsyncSession, proposal_id: UUID
) -> tuple[UUID | None, Sequence[ProposalRow]] | None:
    """T-04-T15: an approved proposal's engagement and its rows, for the owner's applier; None
    when it is not approved (an applier never writes a pending or rejected change)."""
    found = await session.get(Proposal, proposal_id)
    if found is None or found.state not in ("approved", "approved_with_edits"):
        return None
    return found.engagement_id, await rows_of(session, proposal_id)
