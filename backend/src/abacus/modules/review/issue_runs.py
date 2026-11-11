"""What an issue's fix and Explain runs did (T-04-T31; TASK-6819; DEC-3413; P-04 SHL-15 a', a'', d;
T-04 AC-4.3 to AC-4.5). PROTECTED (review).

- **Runs.** Set Fix Instructions and Explain… are a person's acts; the run each starts is recorded
  in that person's transaction (`issue_runs`, purpose `fix` or `explain`), so a run can only ever
  write for the issue a person pointed it at.
- **The fix's proposal.** A fix run that proposes names its proposal once (`issue_fix_proposals`,
  written by the agent, checked against the run's own `issue_runs` row). The proposal is decided
  in SHL-10 like any other.
- **Resolution.** When a person approves that proposal (`proposal.decided`, approved or approved
  with edits), the issue resolves **as that person** (ISSUE-001,
  `issue_events_resolution_by_a_person`): the decider's live membership is read fresh and must
  hold `issue.resolve` on the issue's record; a rejection leaves the issue In progress for the
  person to act on. The agent never resolves.
- **Explanations.** Explain's text is stored sealed with the citation ids that verified, and
  nothing else (`issue_explanations`, `issue.explained`); it decides nothing.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Final, Literal, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import OutboxEvent, Ref, Scope, Target, uow
from abacus.modules.identity.api import AgentContext, AuthContext, Forbidden, authorise
from abacus.modules.review.issues import SUBJECT, issue_row, record_of
from abacus.modules.review.sealing import open_text, seal_text

Purpose = Literal["fix", "explain"]
APPROVED: Final = frozenset({"approved", "approved_with_edits"})
RESOLVABLE: Final = frozenset({"open", "in_progress", "reopened"})


class IssueRunMismatch(DomainConflict):
    """The run writing for an issue is not the run a person started for it."""

    code = "issue_run_mismatch"


_RUN_ROW: Final = text(
    "INSERT INTO issue_runs (tenant_id, issue_id, agent_run_id, purpose) VALUES (:t, :i, :r, :p)"
)
_RUN_OF: Final = text("SELECT issue_id, purpose FROM issue_runs WHERE agent_run_id = :r")
_FIX_PROPOSAL: Final = text(
    "INSERT INTO issue_fix_proposals (tenant_id, issue_id, agent_run_id, proposal_id) "
    "VALUES (:t, :i, :r, :p) ON CONFLICT (tenant_id, agent_run_id) DO NOTHING RETURNING id"
)
_EXPLANATION: Final = text(
    "INSERT INTO issue_explanations (tenant_id, issue_id, agent_run_id, text_sealed, "
    "citation_ids) VALUES (:t, :i, :r, :sealed, CAST(:cites AS uuid[])) RETURNING id"
)
_EVENT: Final = text(
    "INSERT INTO issue_events (tenant_id, issue_id, event, fix_instructions_sealed, scope) "
    "VALUES (:t, :i, :event, NULL, NULL)"
)
_LATEST_INSTRUCTIONS: Final = text(
    "SELECT fix_instructions_sealed FROM issue_events WHERE issue_id = :i "
    "AND event = 'fix_instructions_set' ORDER BY created_at DESC, id DESC LIMIT 1"
)
_ISSUE_OF_PROPOSAL: Final = text(
    "SELECT issue_id, agent_run_id FROM issue_fix_proposals WHERE proposal_id = :p"
)
_RESOLVE: Final = text(
    "UPDATE issues SET status = 'resolved', version = version + 1 WHERE id = :id "
    "AND version = :v AND status IN ('open', 'in_progress', 'reopened') RETURNING id"
)


async def record_issue_run(
    ctx: AuthContext, issue_id: UUID, run_id: UUID, purpose: Purpose
) -> None:
    """In the person's own transaction, after their run started."""
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            _RUN_ROW, {"t": ctx.tenant_id, "i": issue_id, "r": run_id, "p": purpose}
        )


async def _run_for(agent: AgentContext, issue_id: UUID, purpose: Purpose) -> None:
    async with tenant_session(agent.tenant) as session:
        row = (await session.execute(_RUN_OF, {"r": agent.agent_run_id})).first()
    if row is None or row.issue_id != issue_id or row.purpose != purpose:
        raise IssueRunMismatch


async def fix_instructions_of(agent: AgentContext, issue_id: UUID) -> str | None:
    """The sealed instructions the person set, for the issue's own fix run only."""
    await _run_for(agent, issue_id, "fix")
    async with tenant_session(agent.tenant) as session:
        sealed = await session.scalar(_LATEST_INSTRUCTIONS, {"i": issue_id})
    if sealed is None:
        return None
    return await open_text(
        agent.tenant, cast(bytes, sealed), SUBJECT, issue_id, "fix_instructions"
    )


async def record_fix_proposal(agent: AgentContext, issue_id: UUID, proposal_id: UUID) -> None:
    """The fix run's proposal, once per run (a replayed activity writes nothing new)."""
    await _run_for(agent, issue_id, "fix")
    current = await issue_row(agent.tenant, issue_id)
    async with uow(agent.tenant) as tx:
        written = await tx.session.scalar(
            _FIX_PROPOSAL,
            {
                "t": agent.tenant.tenant_id,
                "i": issue_id,
                "r": agent.agent_run_id,
                "p": proposal_id,
            },
        )
        if written is None:
            return
        tx.record(
            "issue.fix_proposed",
            target=Target(SUBJECT, issue_id),
            after=Ref(proposal=str(proposal_id)),
            scope=Scope(engagement_id=current.engagement_id),
        )


async def record_explanation(
    agent: AgentContext, issue_id: UUID, body: str, citation_ids: Sequence[UUID]
) -> UUID:
    """Explain's verified text (the caller kept only verified citations and code's numbers)."""
    await _run_for(agent, issue_id, "explain")
    current = await issue_row(agent.tenant, issue_id)
    sealed = await seal_text(
        agent.tenant, body, SUBJECT, issue_id, "explanation", agent.agent_run_id
    )
    async with uow(agent.tenant) as tx:
        explanation = cast(
            UUID,
            await tx.session.scalar(
                _EXPLANATION,
                {
                    "t": agent.tenant.tenant_id,
                    "i": issue_id,
                    "r": agent.agent_run_id,
                    "sealed": sealed,
                    "cites": [str(c) for c in citation_ids],
                },
            ),
        )
        await tx.session.execute(
            _EVENT, {"t": agent.tenant.tenant_id, "i": issue_id, "event": "explained"}
        )
        tx.record(
            "issue.explained",
            target=Target(SUBJECT, issue_id),
            after=Ref(citations=len(citation_ids)),
            scope=Scope(engagement_id=current.engagement_id),
        )
    return explanation


async def resolve_on_approval(
    tenant_id: UUID, proposal_id: UUID, decision: str, by_user: UUID
) -> UUID | None:
    """The issue whose fix proposal `by_user` approved, resolved as them; None when the proposal
    is no fix, the decision is not an approval, or the issue is no longer open."""
    if decision not in APPROVED:
        return None
    reader = TenantContext(tenant_id, "system", f"proposal:{proposal_id}")
    async with tenant_session(reader) as session:
        row = (await session.execute(_ISSUE_OF_PROPOSAL, {"p": proposal_id})).first()
    if row is None:
        return None
    issue_id = cast(UUID, row.issue_id)
    from abacus.modules.identity.api import member_context

    person = await member_context(tenant_id, by_user)
    if person is None:  # the approver left the firm since: the issue stays for a person
        return None
    return await _resolve_as(person, tenant_id, issue_id, proposal_id)


async def _resolve_as(
    person: AuthContext, tenant_id: UUID, issue_id: UUID, proposal_id: UUID
) -> UUID | None:
    """The resolution, as the approving person (`issue.resolve` on the issue's record)."""
    try:
        current = await issue_row(person.tenant, issue_id)
    except NotFound:
        return None
    if current.status not in RESOLVABLE:
        return None
    _, resource, _ = await record_of(person, current.record_type, current.record_id)
    try:
        await authorise(person, "issue.resolve", resource)
    except Forbidden:
        return None  # approving the values is not the right to resolve: a person resolves later
    async with uow(person.tenant) as tx:
        moved = await tx.session.scalar(_RESOLVE, {"id": issue_id, "v": current.version})
        if moved is None:
            return None
        await tx.session.execute(_EVENT, {"t": tenant_id, "i": issue_id, "event": "resolved"})
        tx.record(
            "issue.resolved",
            target=Target(SUBJECT, issue_id),
            before=Ref(version=current.version),
            after=Ref(version=current.version + 1, proposal=str(proposal_id)),
            scope=Scope(engagement_id=current.engagement_id),
        )
    return issue_id


# --- T-04-T29: the issue detail's read side (SHL-15 a', a'', d) ----------------------------------


@dataclass(frozen=True)
class FixInstructionsRead:
    text: str
    scope: str
    set_by: UUID | None
    set_at: datetime


@dataclass(frozen=True)
class FixRunRead:
    agent_run_id: UUID
    proposal_id: UUID | None


@dataclass(frozen=True)
class ExplanationRead:
    id: UUID
    text: str
    agent_run_id: UUID
    explained_at: datetime
    citation_ids: tuple[UUID, ...]


_INSTRUCTIONS_ROW: Final = text(
    "SELECT fix_instructions_sealed, scope, actor_id, created_at FROM issue_events "
    "WHERE issue_id = :i AND event = 'fix_instructions_set' "
    "ORDER BY created_at DESC, id DESC LIMIT 1"
)
_LATEST_FIX: Final = text(
    "SELECT r.agent_run_id, p.proposal_id FROM issue_runs r LEFT JOIN issue_fix_proposals p "
    "ON p.agent_run_id = r.agent_run_id WHERE r.issue_id = :i AND r.purpose = 'fix' "
    "ORDER BY r.created_at DESC, r.id DESC LIMIT 1"
)
_EXPLANATIONS: Final = text(
    "SELECT id, agent_run_id, text_sealed, citation_ids, created_at FROM issue_explanations "
    "WHERE issue_id = :i ORDER BY created_at, id"
)


def _uuid_or_none(raw: object) -> UUID | None:
    try:
        return UUID(str(raw))
    except ValueError:
        return None


async def issue_run_facts(
    tenant: TenantContext, issue_id: UUID
) -> tuple[FixInstructionsRead | None, FixRunRead | None, list[ExplanationRead]]:
    """What the issue's fix and Explain runs left, for a reader the caller already authorised on
    `issue.read` (the detail route): the instructions, the latest fix run and its proposal, and
    every explanation with the citations it kept."""
    async with tenant_session(tenant) as session:
        instr = (await session.execute(_INSTRUCTIONS_ROW, {"i": issue_id})).first()
        fix = (await session.execute(_LATEST_FIX, {"i": issue_id})).first()
        rows = (await session.execute(_EXPLANATIONS, {"i": issue_id})).all()
    instructions = None
    if instr is not None and instr.fix_instructions_sealed is not None:
        instructions = FixInstructionsRead(
            await open_text(
                tenant, cast(bytes, instr.fix_instructions_sealed), SUBJECT, issue_id,
                "fix_instructions",
            ),
            str(instr.scope or "this_issue"),
            _uuid_or_none(instr.actor_id),
            cast(datetime, instr.created_at),
        )  # fmt: skip
    run = None if fix is None else FixRunRead(fix.agent_run_id, fix.proposal_id)
    explanations = [
        ExplanationRead(
            r.id,
            await open_text(
                tenant,
                cast(bytes, r.text_sealed),
                SUBJECT,
                issue_id,
                "explanation",
                r.agent_run_id,
            ),
            r.agent_run_id,
            cast(datetime, r.created_at),
            tuple(r.citation_ids or ()),
        )
        for r in rows
    ]
    return instructions, run, explanations


async def on_proposal_decided(event: OutboxEvent) -> None:
    payload = event.payload
    await resolve_on_approval(
        event.tenant_id,
        UUID(str(payload["proposal_id"])),
        str(payload["decision"]),
        UUID(str(payload["by_user"])),
    )


SUBSCRIPTIONS: Final = {"proposal.decided": on_proposal_decided}

__all__ = [
    "SUBSCRIPTIONS",
    "IssueRunMismatch",
    "fix_instructions_of",
    "on_proposal_decided",
    "record_explanation",
    "record_fix_proposal",
    "record_issue_run",
    "resolve_on_approval",
]
