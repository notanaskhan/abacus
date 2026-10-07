"""Agent runs and screening (ADR-005, ADR-019, ADR-025, ADR-047, ADR-050, ADR-054, ADR-066).
PROTECTED. TASK-011 design §1, §3-6.

    run_id = await create_screening_run(tenant_id, evidence_version_id, source_event_id)
    agent = await load_agent_context(tenant_id, run_id)
    outcome = await screen(agent)

A run is created for the person the evidence was added for (the initiator, Q1: carried on
`evidence_version.created` as `requested_by`) and the spec's task scope. The agent context is
proven from the run row, with the initiator's live membership, and `authorise` intersects the two
(ADR-025). Screening builds its context from figures code computes from the evidence spreadsheet
itself (ADR-050), calls the gateway, verifies every citation against the spreadsheet (ADR-066)
and records a proposal (ADR-005). It never changes the request item's status (Q2). Invalid output
is repaired once, then the run is escalated with no result.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from abacus.ai_gateway import (
    MAX_ROWS,
    Attribution,
    BudgetExceeded,
    CallTooLarge,
    ContextBuilder,
    ContextTooLarge,
    DatasetTooLarge,
    GatewayCall,
    GatewayRefused,
    call,
    sanitise_text,
)
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import MissingAuditEvent, Ref, Target, uow
from abacus.modules.agents.citations import SheetLayoutError, facts, verify
from abacus.modules.agents.handoff import ScreeningOutput, VerifiedCitation
from abacus.modules.agents.models import AgentRun, ScreeningResult
from abacus.modules.agents.repository import (
    finish_run,
    get_run,
    insert_run,
    insert_screening_result,
    latest_result_for_version,
    latest_results,
    lock_run,
    result_for_run,
    run_for_event,
    set_queued,
    try_lock_run,
)
from abacus.modules.agents.spec import spec
from abacus.modules.engagements.api import get_ref, lock_ref
from abacus.modules.evidence.api import Proposal, read_content, version_view
from abacus.modules.identity.api import (
    AgentContext,
    AuthContext,
    Forbidden,
    agent_context_for_run,
    authorise,
    is_active_member,
)
from abacus.modules.requests.api import fulfilled_items

SCREENER = "evidence.screener"


class AgentRunBusy(Exception):
    """Another attempt is screening this run now (a retry overlapping a timed-out attempt)."""


class AgentRunNotRunning(Exception):
    def __init__(self, status: str) -> None:
        super().__init__(status)
        self.status = status


@dataclass(frozen=True)
class ScreeningOutcome:
    run_id: UUID
    status: str  # completed | escalated
    screening_result_id: UUID | None
    citations: tuple[VerifiedCitation, ...]


def _reader(tenant_id: UUID, label: str) -> TenantContext:
    return TenantContext(tenant_id, "system", label)


async def create_screening_run(
    tenant_id: UUID,
    evidence_version_id: UUID,
    source_event_id: UUID,
    requested_by: UUID | None,
) -> UUID | None:
    """The screener's run for this evidence version, once per event, on behalf of `requested_by`
    (from the event). None without one: an agent never acts for no one. Only retrieved trial
    balances are screened today (they carry a ledger snapshot)."""
    if requested_by is None or not await is_active_member(tenant_id, requested_by):
        return None  # nobody (still) to act for; an at-least-once event mustn't retry forever
    initiator = requested_by
    screener = spec(SCREENER)
    reader = _reader(tenant_id, f"agents:{screener.id}")
    version = await version_view(reader, evidence_version_id)
    if version.snapshot_id is None:
        return None
    run_id: UUID | None = None
    try:
        async with uow(reader) as tx:
            run_id = await insert_run(
                tx.session,
                tenant_id=tenant_id,
                agent_id=screener.id,
                spec_version=screener.version,
                engagement_id=version.engagement_id,
                evidence_version_id=evidence_version_id,
                initiator_user_id=initiator,
                source_event_id=source_event_id,
                task_scope=sorted(screener.task_scope),
            )
            if run_id is None:
                existing = await run_for_event(tx.session, screener.id, source_event_id)
                run_id = existing.id if existing is not None else None
            else:
                tx.record(
                    "agent_run.started",
                    target=Target("agent_run", run_id),
                    after=Ref(evidence_version_id=evidence_version_id, initiator=initiator),
                )
    except MissingAuditEvent:
        pass  # the run already existed: nothing to commit
    return run_id


async def fail_run(tenant_id: UUID, run_id: UUID, code: str) -> bool:
    """End a running run as failed (`agent_run.failed`). Idempotent: False if it already ended."""
    try:
        async with uow(_reader(tenant_id, f"agent-run:{run_id}")) as tx:
            if await finish_run(tx.session, run_id, status="failed", failure_code=code):
                # The code is on the run row (`failure_code`); audit references are identifiers.
                tx.record("agent_run.failed", target=Target("agent_run", run_id))
    except MissingAuditEvent:
        return False  # it had already ended: nothing written
    return True


async def running_engagement(tenant_id: UUID, run_id: UUID) -> UUID | None:
    """The engagement of a running run (for its work slot); None once it has ended."""
    async with tenant_session(_reader(tenant_id, f"agent-run:{run_id}")) as session:
        run = await get_run(session, run_id)
    if run is None:
        raise NotFound("agent_run")
    return run.engagement_id if run.status == "running" else None


async def mark_queued(
    tenant_id: UUID, run_id: UUID, reason: str | None, estimated_start_at: datetime | None
) -> None:
    """The run waits for a work slot (`reason`), or runs again (None) (SPEC-003 AC-13). Audited
    only when that changes (`agent_run.queued`, `agent_run.resumed`), not on every ask."""
    try:
        async with uow(_reader(tenant_id, f"agent-run:{run_id}")) as tx:
            locked = await lock_run(tx.session, run_id)
            if locked is None or locked.status != "running" or locked.queued_reason == reason:
                return
            await set_queued(tx.session, run_id, reason, estimated_start_at)
            event = "agent_run.queued" if reason is not None else "agent_run.resumed"
            tx.record(event, target=Target("agent_run", run_id))
    except MissingAuditEvent:
        pass  # nothing changed: nothing to commit


@dataclass(frozen=True)
class RunOutcome:
    status: str  # running | completed | escalated | failed
    failure_code: str | None
    screening_result_id: UUID | None


async def run_outcome(tenant_id: UUID, run_id: UUID) -> RunOutcome:
    """What a run recorded, for a workflow retry that finds the work already done."""
    async with tenant_session(_reader(tenant_id, f"agent-run:{run_id}")) as session:
        run = await get_run(session, run_id)
        result_id = await result_for_run(session, run_id) if run is not None else None
    if run is None:
        raise NotFound("agent_run")
    return RunOutcome(run.status, run.failure_code, result_id)


async def load_agent_context(tenant_id: UUID, run_id: UUID) -> AgentContext:
    """The agent's context, proven from its running run row and its initiator's live membership
    (a revoked initiator ends the agent's rights: `NoActiveTenant`). The task scope is the run's,
    intersected with the agent's current spec; a run from another spec version is failed."""
    async with tenant_session(_reader(tenant_id, f"agent-run:{run_id}")) as session:
        run = await get_run(session, run_id)
    if run is None:
        raise NotFound("agent_run")
    if run.status != "running":
        raise AgentRunNotRunning(run.status)
    current = spec(run.agent_id)
    if run.spec_version != current.version:
        await fail_run(tenant_id, run.id, "spec_version_changed")
        raise AgentRunNotRunning("failed")
    return await agent_context_for_run(
        tenant_id=tenant_id,
        run_id=run.id,
        agent_id=run.agent_id,
        engagement_id=run.engagement_id,
        task_scope=frozenset(run.task_scope) & current.task_scope,
        initiator_user_id=run.initiator_user_id,
    )


async def _run(agent: AgentContext) -> AgentRun:
    async with tenant_session(agent.tenant) as session:
        run = await get_run(session, agent.agent_run_id)
    if run is None or run.engagement_id != agent.engagement_id:
        raise NotFound("agent_run")
    return run


# Errors that will happen again on retry end the run; provider outages don't (the caller retries).
TERMINAL: dict[type[Exception], str] = {
    SheetLayoutError: "unreadable_evidence",
    DatasetTooLarge: "context_too_large",
    ContextTooLarge: "context_too_large",
    BudgetExceeded: "budget_exceeded",
    CallTooLarge: "context_too_large",
    GatewayRefused: "gateway_refused",
    Forbidden: "forbidden",
    NotFound: "not_found",
}


def _sanitised(citation: dict[str, object]) -> dict[str, object]:
    """A citation with its model-written text sanitised (ADR-065)."""
    return {
        k: sanitise_text(v) if k in ("quote", "value") and isinstance(v, str) else v
        for k, v in citation.items()
    }


async def screen(agent: AgentContext) -> ScreeningOutcome:
    """Screen the run's evidence version. Terminal errors fail the run (`fail_run`) and re-raise;
    `ProviderError` and `AgentRunBusy` leave it running for a retry. One activity in 011b: a
    retry after a failed final write calls the model again; its spend counts against the run's
    budget."""
    try:
        # One attempt at a time per run, so overlapping retries can't both pass the budget check.
        async with tenant_session(agent.tenant) as session:
            if not await try_lock_run(session, agent.agent_run_id):
                raise AgentRunBusy(str(agent.agent_run_id))
            return await _screen(agent)
    except tuple(TERMINAL) as exc:
        code = next(c for kind, c in TERMINAL.items() if isinstance(exc, kind))
        await fail_run(agent.tenant_id, agent.agent_run_id, code)
        raise


async def _screen(agent: AgentContext) -> ScreeningOutcome:
    run = await _run(agent)
    if run.evidence_version_id is None:
        raise NotFound("evidence_version")
    screener = spec(run.agent_id)
    engagement = await get_ref(agent, agent.engagement_id)
    await authorise(agent, "evidence.read", engagement.resource())
    version = await version_view(agent.tenant, run.evidence_version_id)
    if version.period_start is None or version.period_end is None:
        raise NotFound("evidence_period")
    content = await read_content(agent.tenant, version.stored)
    # Code computes; the model judges (ADR-050): totals and positions, never rows of amounts.
    sheet = facts(content)
    items = await fulfilled_items(agent.tenant, version.id)
    period = f"{version.period_start.isoformat()} to {version.period_end.isoformat()}"
    context = (
        ContextBuilder()
        .text("engagement", f"Requested period {period}.")
        .task(
            {
                "request_items": [
                    {"description": i.description, "audit_area": i.audit_area} for i in items
                ],
                "period": {
                    "start": version.period_start.isoformat(),
                    "end": version.period_end.isoformat(),
                },
                "line_count": sheet.line_count,
                "totals": {"debit": str(sheet.total_debit), "credit": str(sheet.total_credit)},
                "balanced": sheet.total_debit == sheet.total_credit,
                "total_row_matches_lines": sheet.total_row_matches,
                "cells": {
                    "total_debit": f"C{sheet.total_row}",
                    "total_credit": f"D{sheet.total_row}",
                    "first_line": "A2",
                    "last_line": f"D{sheet.last_line_row}",
                },
                "account_names": list(sheet.account_names[:MAX_ROWS]),
            },
            untrusted=screener.untrusted_inputs,
            trim="account_names",
        )
        .build()
    )
    result = await call(
        GatewayCall(
            purpose=screener.purpose,
            prompt=screener.prompt,
            tier=screener.tier,
            output_schema=ScreeningOutput,
            budget_usd=screener.limits.max_cost_usd,
            attribution=Attribution(agent.tenant, agent.engagement_id, run.agent_id, run.id),
            context=context,
            work_class=screener.work_class,
            essential=screener.essential,
            cheaper_tiers=screener.cheaper_tiers,
            max_output_tokens=screener.limits.max_output_tokens,
            timeout_seconds=screener.limits.max_seconds,
        )
    )
    if result.output is None:
        async with uow(agent.tenant) as tx:
            if await finish_run(
                tx.session, run.id, status="escalated", context_hash=context.sha256
            ):
                tx.record("agent_run.escalated", target=Target("agent_run", run.id))
        return ScreeningOutcome(run.id, "escalated", None, ())
    output = result.output
    checked = tuple(verify(content, list(output.citations)))
    unverified = [*output.unverified] + [
        f"citation {c.cell}: {c.reason}" for c in checked if not c.verified
    ]
    # Code has the last word on what it can check (ADR-066): a claim it can't verify, or figures
    # that don't add up, never reach a reviewer as "ready".
    if sheet.total_debit != sheet.total_credit:
        unverified.append("debits and credits differ")
    if not sheet.total_row_matches:
        unverified.append("the sheet's Total row differs from its lines")
    if context.truncated:
        unverified.append("only part of the account list was screened")
    action = output.action
    if Decimal(str(output.confidence)) < screener.confidence_routing.below:
        action = screener.confidence_routing.route
    if (
        any(not c.verified for c in checked)
        or sheet.total_debit != sheet.total_credit
        or not sheet.total_row_matches
    ):
        action = "needs_revision"
    result_id: UUID | None = None
    async with uow(agent.tenant) as tx:
        locked = await lock_run(tx.session, run.id)
        if locked is None or locked.status != "running":
            raise AgentRunNotRunning(locked.status if locked else "missing")
        locked_engagement = await lock_ref(tx, agent.engagement_id)
        await authorise(agent, "screening.run", locked_engagement.resource())
        result_id = await insert_screening_result(
            tx.session,
            values={
                "tenant_id": agent.tenant_id,
                "engagement_id": agent.engagement_id,
                "evidence_version_id": version.id,
                "agent_run_id": run.id,
                "action": action,
                "confidence": Decimal(str(output.confidence)).quantize(Decimal("0.001")),
                # Model text is stored sanitised (ADR-065; SPEC-006 AC-1).
                "rationale": sanitise_text(output.rationale),
                "citations": [_sanitised(c.model_dump()) for c in checked],
                "unverified": [sanitise_text(u) for u in unverified],
            },
        )
        await finish_run(
            tx.session,
            run.id,
            status="completed",
            context_hash=context.sha256,
            output=cast(dict[str, object], output.model_dump(mode="json")),
        )
        tx.record(
            "screening_result.created",
            target=Target("screening_result", result_id),
            after=Ref(agent_run_id=run.id, evidence_version_id=version.id),
        )
    return ScreeningOutcome(run.id, "completed", result_id, checked)


@dataclass(frozen=True)
class ScreeningResultView:
    """An agent's proposal about an evidence version, as the evidence board shows it. The
    rationale and quotes are model text: the UI renders them as sanitised plain text (ADR-065)."""

    id: UUID
    evidence_version_id: UUID
    action: str
    confidence: Decimal
    rationale: str
    citations: list[dict[str, object]]
    unverified: list[str]
    created_at: datetime


async def screening_results_for(
    ctx: AuthContext, engagement_id: UUID
) -> list[ScreeningResultView]:
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "evidence.read", ref.resource())
    async with tenant_session(ctx.tenant) as session:
        rows = await latest_results(session, ctx, engagement_id)
    if rows:
        # Results quote evidence content (cells, values): their reads are audited like
        # `evidence_version.read` (ADR-104; security review, TASK-012).
        async with uow(ctx.tenant) as tx:
            tx.record("screening_result.read", target=Target("engagement", engagement_id))
    return [
        ScreeningResultView(
            r.id,
            r.evidence_version_id,
            r.action,
            r.confidence,
            r.rationale,
            r.citations,
            r.unverified,
            r.created_at,
        )
        for r in rows
    ]


# --- Proposals for review queues (SPEC-004; TASK-019 D1) -----------------------------------------


def _proposal(r: ScreeningResult) -> Proposal:
    return Proposal(r.id, r.action, r.confidence, r.rationale, r.citations, r.unverified)


async def proposals_for(ctx: AuthContext, engagement_id: UUID) -> dict[UUID, Proposal]:
    """The latest proposal per version, for the review queue: read like the evidence board's
    screening results (authorised `evidence.read`, and audited when any is shown)."""
    results = await screening_results_for(ctx, engagement_id)
    return {
        r.evidence_version_id: Proposal(
            r.id, r.action, r.confidence, r.rationale, r.citations, r.unverified
        )
        for r in results
    }


async def proposal_of(session: AsyncSession, evidence_version_id: UUID) -> Proposal | None:
    """The latest proposal about one version, read in the caller's transaction (a decision the
    caller has authorised), so it sees what the decision commits against."""
    found = await latest_result_for_version(session, evidence_version_id)
    return _proposal(found) if found is not None else None
