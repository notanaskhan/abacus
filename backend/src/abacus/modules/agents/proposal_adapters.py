"""Typed proposal adapters for the live specialists (P-04-T25, TASK-1461; ADR-161 clause 3;
DEC-603, DEC-604, DEC-608).

The screener's results, the upload reviewer's findings and the matcher's proposals stay in their
own tables (they are not migrated). These adapters project one row of each as the C3 proposal
SHL-10 renders (`GET /v1/proposals/screening_result:<id>`, `upload_review:<id>`,
`inbox_match:<id>`), with the citations C4 verified for it, and map a person's verdict onto the
path that exists today:

- **Screening result, upload review.** Approve is AUD-03's Accept: `evidence.api.decide(...,
  "accept", seen_proposal=<the screener's latest result>)`, the very call the evidence route makes,
  so the same `review_decisions` row is written (REVIEW-001's path, with its own matrix action,
  independence and database checks) and the request reads "Received". Reject is AUD-03's Send
  back, with the reason mapped to a platform reason code (DEC-603), so the file goes back to the
  client with that reason.
- **Inbox match.** Approve assigns the file to the matcher's first shown request (the inbox's own
  assign, recorded as a followed matcher suggestion). Reject records the person's verdict and
  leaves the file waiting in the inbox for someone to sort.
- A run in shadow, or a firm whose stage for that agent is shadow, shows no proposal: 404, so
  SHL-10 never opens (SPEC-036 AC-5; DEC-608). Synthetic firms have no stages.
- A typed proposal has one version (1); a newer result for the same file or a decision already
  made answers 409 `proposal_changed`. Every row must be cited (422 `uncited_change`) before an
  approval reaches evidence.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Final, Literal
from uuid import UUID

from abacus.kernel.clock import system_now
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import Ref, Scope, Target, uow
from abacus.modules.agents.models import AgentRun
from abacus.modules.agents.proposal_store import (
    match_with_proposals,
    newest_match,
    newest_upload_review,
    run_of,
    screening_result,
    upload_review_with_flags,
)
from abacus.modules.agents.proposals import (
    APPROVE,
    READ,
    REASONS,
    REJECT,
    DecisionView,
    EvidenceView,
    ProposalChanged,
    ProposalInvalid,
    ProposalView,
    RowView,
)
from abacus.modules.agents.service import proposal_of
from abacus.modules.agents.stages import starts_in_shadow
from abacus.modules.engagements.api import get_ref, lock_ref
from abacus.modules.evidence.api import (
    assign_inbox_file,
    decide,
    effective_decisions,
    screening_facts,
    verified_citation_ids,
    waiting_among,
    withdrawn_among,
)
from abacus.modules.identity.api import (
    AuthContext,
    Resource,
    allowed_actions,
    authorise,
    names_of,
)
from abacus.modules.review.api import UncitedChange

KINDS: Final = ("screening_result", "upload_review", "inbox_match")
_REF: Final = re.compile(
    r"(screening_result|upload_review|inbox_match):"
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"
)
# DEC-603: a proposal's reason, as the platform reason code a send-back carries.
SEND_BACK_REASON: Final = {
    "needs_client_input": "incomplete",
    "unsupported_value": "does_not_agree",
    "wrong_treatment": "other",
    "other": "other",
}
_STATE_OF: Final = {"accept": "approved", "reject": "rejected", "send_back": "rejected"}


@dataclass(frozen=True)
class _Projected:
    view: ProposalView
    engagement_id: UUID
    subject_id: UUID  # the version (screening, upload review) or the inbox file (match)
    resource: Resource
    first_request_item_id: UUID | None = None


def parse(ref: str) -> tuple[str, UUID] | None:
    """`kind:<uuid>` for a typed adapter's ref, or None for a plain proposal UUID."""
    found = _REF.fullmatch(ref)
    return (found.group(1), UUID(found.group(2))) if found else None


async def _hidden(tenant: TenantContext, run: AgentRun) -> bool:
    """SPEC-036 AC-5 and P-04-T25: a shadow run's output, or anything while the firm's stage for
    that agent is shadow, is never a proposal."""
    if run.shadow:
        return True
    async with tenant_session(tenant) as session:
        return await starts_in_shadow(session, tenant, run.agent_id)


async def _resource(ctx: AuthContext, engagement_id: UUID) -> Resource:
    ref = await get_ref(ctx, engagement_id)
    resource = ref.resource()
    await authorise(ctx, READ, resource)  # a wall answers 404
    return resource


async def _allowed(ctx: AuthContext, resource: Resource, state: str) -> list[str]:
    if state != "pending" or ctx.tenant.actor_kind != "human" or ctx.client or ctx.is_support:
        return []
    found = await allowed_actions(ctx, resource, (APPROVE, REJECT))
    return [a for a in (APPROVE, REJECT) if a in found]


def _citations(
    found: dict[tuple[UUID, str | None], list[UUID]], anchor: UUID, ref: str | None
) -> list[UUID]:
    return list(found.get((anchor, ref), []))


async def _on_version(
    ctx: AuthContext,
    kind: Literal["screening_result", "upload_review"],
    subject: UUID,
    run: AgentRun,
    engagement_id: UUID,
    version_id: UUID,
    newest: bool,
    rows: list[RowView],
    reasoning: str,
) -> _Projected:
    resource = await _resource(ctx, engagement_id)
    decisions = await effective_decisions(ctx.tenant, [version_id])
    gone = version_id in await withdrawn_among(ctx.tenant, [version_id])
    decided = decisions.get(version_id)
    state = (
        _STATE_OF.get(decided, "superseded")
        if decided is not None
        else ("superseded" if gone or not newest else "pending")
    )
    facts = await screening_facts(ctx.tenant, [version_id])
    label = facts[version_id].file_name if version_id in facts else ""
    cited = sum(len(r.citation_ids) for r in rows)
    view = ProposalView(
        ref=f"{kind}:{subject}",
        kind=kind,
        title=label,
        context_label="",
        state=state,
        version=1,
        agent_run_id=run.id,
        proposed_at=run.finished_at or run.started_at,
        change_count=len(rows),
        reasoning=reasoning,
        rows=rows,
        totals=[],
        evidence=[EvidenceView(version_id, label, cited)] if cited else [],
        policy=None,
        set=None,
        checkpoint_id=None,
        decision=None,
        allowed_actions=await _allowed(ctx, resource, state),
    )
    return _Projected(view, engagement_id, version_id, resource)


async def _visible_run(ctx: AuthContext, run: AgentRun | None) -> AgentRun:
    if run is None or await _hidden(ctx.tenant, run):
        raise NotFound("proposal")
    return run


async def _project_screening(ctx: AuthContext, subject: UUID) -> _Projected:
    async with tenant_session(ctx.tenant) as session:
        result = await screening_result(session, subject)
        if result is None:
            raise NotFound("proposal")
        run = await run_of(session, result.agent_run_id)
        latest = await proposal_of(session, result.evidence_version_id)
    run = await _visible_run(ctx, run)
    current = latest is not None and latest.screening_result_id == result.id
    cited = _citations(
        await verified_citation_ids(ctx.tenant, "screening_result", [result.id]), result.id, None
    )
    row = RowView(
        n=1,
        suggestion_id=None,
        field_key="evidence_version.review",
        label="Review decision",
        before=None,
        after="accept",
        cause=result.action,
        citation_ids=cited,
        unsupported=not cited,
    )
    return await _on_version(
        ctx,
        "screening_result",
        result.id,
        run,
        result.engagement_id,
        result.evidence_version_id,
        current,
        [row],
        result.rationale,
    )


async def _project_upload_review(ctx: AuthContext, subject: UUID) -> _Projected:
    async with tenant_session(ctx.tenant) as session:
        found = await upload_review_with_flags(session, subject)
        if found is None:
            raise NotFound("proposal")
        review, flags = found
        run = await run_of(session, review.agent_run_id)
        current = await newest_upload_review(session, review.evidence_version_id) == review.id
    run = await _visible_run(ctx, run)
    cited = await verified_citation_ids(ctx.tenant, "upload_review", [review.id])
    rows = [
        RowView(
            n=f.position,
            suggestion_id=None,
            field_key=f"flag.F{f.position}",
            label=f.category,
            before=None,
            after=None,
            cause=f.category,
            citation_ids=_citations(cited, review.id, f"F{f.position}"),
            unsupported=not _citations(cited, review.id, f"F{f.position}"),
        )
        for f in flags
    ]
    return await _on_version(
        ctx,
        "upload_review",
        review.id,
        run,
        review.engagement_id,
        review.evidence_version_id,
        current,
        rows,
        "\n".join(f.rationale for f in flags),
    )


async def _project_match(ctx: AuthContext, subject: UUID) -> _Projected:
    async with tenant_session(ctx.tenant) as session:
        found = await match_with_proposals(session, subject)
        if found is None:
            raise NotFound("proposal")
        match, picks = found
        run = await run_of(session, match.agent_run_id)
        current = await newest_match(session, match.inbox_file_id) == match.id
    await _visible_run(ctx, run)
    resource = await _resource(ctx, match.engagement_id)
    cited = await verified_citation_ids(ctx.tenant, "inbox_match", [match.id])
    waiting = match.inbox_file_id in await waiting_among(ctx.tenant, [match.inbox_file_id])
    state = "pending" if waiting and current and picks else "superseded"
    rows = [
        RowView(
            n=p.rank,
            suggestion_id=None,
            field_key=f"request_item:{p.request_item_id}",
            label=f"Request {p.rank}",
            before=None,
            after=str(p.request_item_id),
            cause="matcher",
            citation_ids=_citations(cited, match.id, f"R{p.rank}"),
            unsupported=not _citations(cited, match.id, f"R{p.rank}"),
        )
        for p in picks
    ]
    view = ProposalView(
        ref=f"inbox_match:{match.id}",
        kind="inbox_match",
        title="",
        context_label="",
        state=state,
        version=1,
        agent_run_id=match.agent_run_id,
        proposed_at=match.created_at,
        change_count=len(rows),
        reasoning="\n".join(p.rationale for p in picks),
        rows=rows,
        totals=[],
        evidence=[],
        policy=None,
        set=None,
        checkpoint_id=None,
        decision=None,
        allowed_actions=await _allowed(ctx, resource, state),
    )
    first = picks[0].request_item_id if picks else None
    return _Projected(view, match.engagement_id, match.inbox_file_id, resource, first)


async def _project(ctx: AuthContext, kind: str, subject: UUID) -> _Projected:
    if kind == "screening_result":
        return await _project_screening(ctx, subject)
    if kind == "upload_review":
        return await _project_upload_review(ctx, subject)
    if kind == "inbox_match":
        return await _project_match(ctx, subject)
    raise NotFound("proposal")


async def adapter_view(ctx: AuthContext, kind: str, subject: UUID) -> ProposalView:
    """`GET /v1/proposals/<kind>:<id>`: the typed row as a C3 proposal."""
    return (await _project(ctx, kind, subject)).view


def _pending(projected: _Projected, seen_version: int) -> None:
    if projected.view.state != "pending" or seen_version != projected.view.version:
        raise ProposalChanged(facts={"version": projected.view.version})


def _cited(rows: Sequence[RowView]) -> None:
    uncited = [r.n for r in rows if r.unsupported]
    if uncited or not rows:
        raise UncitedChange(
            facts={"count": len(uncited) or 1, "row": uncited[0] if uncited else 1}
        )


async def approve_typed(
    ctx: AuthContext, kind: str, subject: UUID, *, seen_version: int
) -> ProposalView:
    """Approve a typed proposal through the path that exists today (ADR-161 clause 3)."""
    projected = await _project(ctx, kind, subject)
    await authorise(ctx, APPROVE, projected.resource)
    _pending(projected, seen_version)
    _cited(projected.view.rows)
    if kind == "inbox_match":
        if projected.first_request_item_id is None:
            raise ProposalChanged(facts={"version": 1})
        written = await assign_inbox_file(
            ctx,
            projected.engagement_id,
            projected.subject_id,
            request_item_id=projected.first_request_item_id,
            followed_suggestion=True,
            suggestion_source="matcher",
            suggestion_rank=1,
        )
    else:
        written = (
            await decide(
                ctx,
                projected.engagement_id,
                projected.subject_id,
                "accept",
                reason_code=None,
                note=None,
                seen_proposal=await _seen(ctx, projected.subject_id),
            )
        ).id
    return await _decided(ctx, kind, subject, "approved", written, None)


async def reject_typed(
    ctx: AuthContext,
    kind: str,
    subject: UUID,
    *,
    seen_version: int,
    reason_code: str,
    note: str | None,
) -> ProposalView:
    """Reject a typed proposal: a send-back with the mapped reason (DEC-603), or, for a match,
    the verdict recorded with the file left waiting."""
    if reason_code not in REASONS:
        raise ProposalInvalid(facts={"field": "reason_code"})
    projected = await _project(ctx, kind, subject)
    await authorise(ctx, REJECT, projected.resource)
    _pending(projected, seen_version)
    if kind == "inbox_match":
        async with uow(ctx.tenant) as tx:
            await lock_ref(tx, projected.engagement_id)
            tx.record(
                "proposal.rejected",
                target=Target("inbox_match", subject),
                after=Ref(version=1),
                scope=Scope(engagement_id=projected.engagement_id),
            )
        return await _decided(ctx, kind, subject, "rejected", subject, reason_code)
    written = await decide(
        ctx,
        projected.engagement_id,
        projected.subject_id,
        "send_back",
        reason_code=SEND_BACK_REASON[reason_code],
        note=(note or "").strip() or None,
        seen_proposal=await _seen(ctx, projected.subject_id),
    )
    return await _decided(ctx, kind, subject, "rejected", written.id, reason_code)


async def _seen(ctx: AuthContext, version_id: UUID) -> UUID | None:
    """The screener's latest result on the version: what AUD-03 shows the person, so the
    decision records whether it corrects the agent (evidence's AC-10)."""
    async with tenant_session(ctx.tenant) as session:
        found = await proposal_of(session, version_id)
    return found.screening_result_id if found is not None else None


async def _decided(
    ctx: AuthContext,
    kind: str,
    subject: UUID,
    decision: str,
    written: UUID,
    reason_code: str | None,
) -> ProposalView:
    """The projection after the verdict, naming the person. The decision lives in the owner's
    row; `decision.id` is that row (the review decision, the new evidence version of an assigned
    inbox file, or for a rejected match the match itself, whose verdict is its audit event)."""
    view = (await _project(ctx, kind, subject)).view
    names = await names_of([ctx.user_id])
    return replace(
        view,
        state=view.state if view.state != "pending" else decision,
        decision=DecisionView(
            id=written,
            decision=decision,
            reason_code=reason_code,
            note=None,
            decided_by_user_id=ctx.user_id,
            decided_by_name=names.get(ctx.user_id, ""),
            decided_at=system_now(),
            routed_to_user_id=None,
            undo_until=None,
        ),
        allowed_actions=[],
    )


__all__ = ["KINDS", "adapter_view", "approve_typed", "parse", "reject_typed"]
