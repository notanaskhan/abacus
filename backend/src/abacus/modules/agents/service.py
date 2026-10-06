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
from decimal import Decimal
from typing import cast
from uuid import UUID

from abacus.ai_gateway import MAX_ROWS, Attribution, ContextBuilder, GatewayCall, call
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import MissingAuditEvent, Ref, Target, uow
from abacus.modules.agents.citations import facts, verify
from abacus.modules.agents.handoff import ScreeningOutput, VerifiedCitation
from abacus.modules.agents.models import AgentRun
from abacus.modules.agents.repository import (
    finish_run,
    get_run,
    insert_run,
    insert_screening_result,
    lock_run,
    run_for_event,
)
from abacus.modules.agents.spec import spec
from abacus.modules.engagements.api import get_ref, lock_ref
from abacus.modules.evidence.api import read_content, version_view
from abacus.modules.identity.api import (
    AgentContext,
    agent_context_for_run,
    authorise,
    initiator_context,
)
from abacus.modules.requests.api import fulfilled_items

SCREENER = "evidence.screener"


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
    if requested_by is None:
        return None
    initiator = requested_by
    reader = _reader(tenant_id, "agents:screening")
    version = await version_view(reader, evidence_version_id)
    if version.snapshot_id is None:
        return None
    screener = spec(SCREENER)
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


async def load_agent_context(tenant_id: UUID, run_id: UUID) -> AgentContext:
    """The agent's context, proven from its running run row and its initiator's live membership
    (a revoked initiator ends the agent's rights: `NoActiveTenant`)."""
    async with tenant_session(_reader(tenant_id, f"agent-run:{run_id}")) as session:
        run = await get_run(session, run_id)
    if run is None:
        raise NotFound("agent_run")
    if run.status != "running":
        raise AgentRunNotRunning(run.status)
    initiator = await initiator_context(tenant_id, run.initiator_user_id)
    return agent_context_for_run(
        tenant_id=tenant_id,
        run_id=run.id,
        agent_id=run.agent_id,
        engagement_id=run.engagement_id,
        task_scope=frozenset(run.task_scope),
        initiator=initiator,
    )


async def _run(agent: AgentContext) -> AgentRun:
    async with tenant_session(agent.tenant) as session:
        run = await get_run(session, agent.agent_run_id)
    if run is None or run.engagement_id != agent.engagement_id:
        raise NotFound("agent_run")
    return run


async def screen(agent: AgentContext) -> ScreeningOutcome:
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
            max_output_tokens=screener.limits.max_output_tokens,
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
    action = output.action
    if Decimal(str(output.confidence)) < screener.confidence_routing.below:
        action = screener.confidence_routing.route
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
                "rationale": output.rationale,
                "citations": [c.model_dump() for c in checked],
                "unverified": unverified,
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
