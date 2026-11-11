"""Workbench session turns, the agents half (P-10-T43; SPEC-647 §3.7 AC-S1 to AC-S5; P-10 §4.4;
ADR-005, ADR-234 proposed; DEC-4301). PROTECTED (agents).

A session's turn is a run, so the gateway, C17, metering and the trace attribute it like any
other: its row is written when the person posts (`open_turn_run`, the person's own context), it
logs into exactly one session (`session_id`, AC-S1) and it runs inline in the session's workflow
(`run_session_turn`), never as an `AgentRunWorkflow`:

- **Read-only.** The turn is offered only the capability's `read` and `compute` tools; a tool
  the turn was not offered is refused (`not_offered`) even if a model names it. So an inline turn
  never proposes or writes.
- **A write-proposing turn plans.** When the turn's structured output is a `plan` (a declared
  write needs approval first), `open_plan_child_run` writes exactly one child run for it
  (`parent_run_id` = the turn, the plan as its deterministic `inputs.plan`, the session owner as
  the approver of each write), and the session's workflow starts that child's `AgentRunWorkflow`,
  which validates the plan and waits in `awaiting_plan_approval` (AC-S4, WB-03a). A retried
  activity finds the child it already wrote.
- **Questions are output fields.** A `question` ends the turn `needs_input`; the person's answer
  is a new turn on the same session (the session's workflow keeps the question open while other
  messages are answered first, AC-S2).

Identifiers, codes and verified blocks cross the activity boundary; the message itself is read
from the session's item by the workbench activity and handed here as the first user turn.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import Ref, Scope, Target, uow
from abacus.modules.agents.conformance import ConversePorts, limits_of
from abacus.modules.agents.harness import ToolRequest, ToolResult, run_step
from abacus.modules.agents.run_activities import complete_run_activity, set_state_activity
from abacus.modules.agents.run_start import COUNTER
from abacus.modules.agents.service import load_run_v2_context
from abacus.modules.agents.spec_v2 import TEST_ONLY, AgentSpecV2, spec_v2
from abacus.modules.agents.tools.registry import registered_tools
from abacus.modules.engagements.api import client_of, get_ref
from abacus.modules.identity.api import AuthContext, Forbidden, authorise, is_synthetic_firm

READ_KINDS: Final = frozenset({"read", "compute"})
_READER: Final = "session-turn"
_SEED = text(
    "INSERT INTO tenant_counters (tenant_id, name, value) SELECT CAST(:t AS uuid), :name, "
    "COALESCE(max(run_number), 0) FROM agent_runs ON CONFLICT (tenant_id, name) DO NOTHING"
)
_NEXT = text("UPDATE tenant_counters SET value = value + 1 WHERE name = :name RETURNING value")
_TURN = text(
    "INSERT INTO agent_runs (tenant_id, agent_id, spec_version, engagement_id, "
    "initiator_user_id, task_scope, state, mode, trigger_kind, run_number, runs_as_user_id, "
    "inputs, session_id) VALUES (:t, :agent, :version, :eng, :by, :scope, 'queued', 'run', "
    "'manual', :number, :by, CAST(:inputs AS jsonb), :session) RETURNING id"
)
_CHILD = text(
    "INSERT INTO agent_runs (tenant_id, agent_id, spec_version, engagement_id, "
    "initiator_user_id, task_scope, state, mode, trigger_kind, run_number, runs_as_user_id, "
    "inputs, session_id, parent_run_id, client_scope) VALUES (:t, :agent, :version, :eng, :by, "
    ":scope, 'queued', 'plan', 'manual', :number, :by, CAST(:inputs AS jsonb), :session, "
    ":parent, :clients) RETURNING id"
)


def read_only_tools(spec: AgentSpecV2) -> frozenset[str]:
    """The tools an inline turn is offered: the spec's `read` and `compute` tools only."""
    found = registered_tools()
    return frozenset(n for n in spec.tools.names() if found[n].kind in READ_KINDS)


def write_actions(spec: AgentSpecV2) -> Mapping[str, str]:
    """Each of the spec's propose and approved_write tools with the action it writes."""
    found = registered_tools()
    return {n: found[n].action for n in spec.tools.names() if found[n].kind not in READ_KINDS}


async def open_turn_run(
    ctx: AuthContext,
    *,
    agent_id: str,
    engagement_id: UUID,
    session_id: UUID,
    inputs: Mapping[str, object],
) -> UUID:
    """The turn's run row for the person posting (module docstring). The caller has authorised
    `session.create` and owns the session; the engagement is read through `get_ref` (a wall
    answers 404) and must be readable."""
    if ctx.tenant.actor_kind != "human" or ctx.client or ctx.is_support:
        raise Forbidden("session.create", "role")
    spec = spec_v2(agent_id)
    if spec.id in TEST_ONLY and not await is_synthetic_firm(ctx.tenant):
        raise NotFound("agent_capability")  # never installable for a real firm (P-10-T40)
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "engagement.read", ref.resource())
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(_SEED, {"t": ctx.tenant_id, "name": COUNTER})
        number = cast(int, await tx.session.scalar(_NEXT, {"name": COUNTER}))
        run_id = cast(
            UUID,
            await tx.session.scalar(
                _TURN,
                {
                    "t": ctx.tenant_id,
                    "agent": spec.id,
                    "version": spec.version,
                    "eng": engagement_id,
                    "by": ctx.user_id,
                    "scope": sorted(spec.task_scope),
                    "number": number,
                    "inputs": json.dumps(dict(inputs), sort_keys=True, default=str),
                    "session": session_id,
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


@dataclass
class ReadOnlyPorts(ConversePorts):
    """`ConversePorts` offering only the spec's read tools; anything else is refused."""

    offered: frozenset[str] = field(default_factory=frozenset[str])

    def __post_init__(self) -> None:
        super().__post_init__()
        self.offered = read_only_tools(self.spec)
        self.tools = tuple(t for t in self.tools if t.spec.name in self.offered)

    async def tool(self, request: ToolRequest) -> ToolResult:
        if request.name not in self.offered:
            return ToolResult(name=request.name, ok=False, code="not_offered")
        return await super().tool(request)


@dataclass(frozen=True)
class TurnOutcome:
    """What the session's workflow and items need from one turn (no client content but the
    verified blocks and the question, which the workbench stores as items)."""

    status: str  # completed · needs_input · plan_proposed · failed
    failure: str | None = None
    blocks: dict[str, Any] | None = None  # Any: verified C6 v2 blocks
    question: dict[str, Any] | None = None  # Any: the structured question
    plan: list[dict[str, Any]] = field(default_factory=list[dict[str, Any]])  # Any: plan steps
    unsupported: int = 0
    records_read: int = 0
    client_scope: list[str] = field(default_factory=list[str])


def _tenant(tenant_id: UUID, run_id: UUID) -> TenantContext:
    return TenantContext(tenant_id, "system", f"{_READER}:{run_id}")


def plan_steps(
    plan: Mapping[str, object], spec: AgentSpecV2, approver_user_id: UUID
) -> list[dict[str, object]]:
    """A turn's proposed plan as the run's deterministic plan: one step per proposed step, in
    order (each depends on the one before), a write step naming the action its tool writes and
    the session owner as its approver. `validate_plan` decides whether it may await approval."""
    raw = plan.get("steps")
    steps = cast(list[Mapping[str, object]], raw if isinstance(raw, list) else [])
    writes = write_actions(spec)
    out: list[dict[str, object]] = []
    for index, step in enumerate(steps):
        key = f"s{index + 1}"
        tool = str(step["tool"]) if step.get("tool") else None
        action = writes.get(tool or "")
        is_write = bool(step.get("write")) or action is not None
        out.append(
            {
                "key": key,
                "label": str(step.get("label") or key),
                "level": index,
                "kind": "tool" if tool else "narration",
                "tool": tool,
                "arguments": {},
                "depends_on": [f"s{index}"] if index else [],
                "writes": [action] if is_write and action else [],
                "approver_user_id": str(approver_user_id) if is_write else None,
                "reads_clients": [],
            }
        )
    return out


async def run_session_turn(tenant_id: UUID, run_id: UUID, request: str) -> TurnOutcome:
    """Run one turn inline (module docstring): `queued → running`, the harness over read-only
    ports, then `succeeded`, `needs_input` (a question) or `failed`. A plan is returned for the
    workbench to hand to `open_plan_child_run`; the turn itself ends `succeeded`."""
    agent = await load_run_v2_context(tenant_id, run_id)
    spec = spec_v2(agent.agent_id)
    if spec.id in TEST_ONLY and not await is_synthetic_firm(agent.tenant):
        raise NotFound("agent_run")
    t, r = str(tenant_id), str(run_id)
    await set_state_activity(t, r, "running", None, None)
    ports = ReadOnlyPorts(agent, spec, 1, request)
    outcome = await run_step(
        ports,
        limits_of(spec),
        facts={},
        citations=set(),
        first_turn={"role": "user", "kind": "session_message"},
    )
    clients = await _record_turn(tenant_id, run_id, outcome.active_ms, outcome.cost_usd)
    if outcome.status == "needs_input" and outcome.question is not None:
        await set_state_activity(t, r, "needs_input", "question", {"kind": "question"})
        return TurnOutcome(
            "needs_input",
            question=dict(outcome.question),
            records_read=outcome.records_read,
            client_scope=clients,
        )
    if outcome.status in ("completed", "plan_proposed"):
        await complete_run_activity(t, r, "succeeded", None)
        return TurnOutcome(
            outcome.status,
            blocks=dict(outcome.blocks) if outcome.blocks is not None else None,
            plan=[dict(s) for s in plan_steps(outcome.plan or {}, spec, agent.initiator.user_id)],
            unsupported=len(outcome.unsupported),
            records_read=outcome.records_read,
            client_scope=clients,
        )
    failure = outcome.failure or "turn_failed"
    await complete_run_activity(t, r, "failed", failure)
    return TurnOutcome("failed", failure=failure, client_scope=clients)


async def _record_turn(tenant_id: UUID, run_id: UUID, active_ms: int, cost: Decimal) -> list[str]:
    """The turn's counters, and the clients it read: the engagement's client plus the run's
    pinned scope (the session's `client_scope` is their union over every turn, AC-S3)."""
    tenant = _tenant(tenant_id, run_id)
    async with uow(tenant) as tx:
        row = (
            await tx.session.execute(
                text(
                    "UPDATE agent_runs SET agent_ms = agent_ms + :ms, cost_usd = cost_usd + :cost "
                    "WHERE id = :run RETURNING engagement_id, client_scope"
                ),
                {"ms": active_ms, "cost": cost, "run": run_id},
            )
        ).one()
        tx.record("agent_run.turn_recorded", target=Target("agent_run", run_id), after=None)
    clients = {str(c) for c in cast(list[UUID], row.client_scope or [])}
    if row.engagement_id is not None:
        client = await client_of(tenant, row.engagement_id)
        if client is not None:
            clients.add(str(client))
    return sorted(clients)


async def open_plan_child_run(
    tenant_id: UUID, turn_run_id: UUID, steps: Sequence[Mapping[str, object]]
) -> UUID:
    """Exactly one child run for a write-proposing turn (AC-S4): copied from the turn's row (its
    capability, engagement, initiator, task scope and session), the plan as its `inputs.plan`.
    A second call for the same turn answers the child already written."""
    tenant = _tenant(tenant_id, turn_run_id)
    async with uow(tenant) as tx:
        parent = (
            await tx.session.execute(
                text(
                    "SELECT agent_id, spec_version, engagement_id, initiator_user_id, task_scope, "
                    "session_id, client_scope FROM agent_runs WHERE id = :run FOR UPDATE"
                ),
                {"run": turn_run_id},
            )
        ).first()
        if parent is None:
            raise NotFound("agent_run")
        existing = await tx.session.scalar(
            text("SELECT id FROM agent_runs WHERE parent_run_id = :run LIMIT 1"),
            {"run": turn_run_id},
        )
        if existing is not None:
            return cast(UUID, existing)
        await tx.session.execute(_SEED, {"t": tenant_id, "name": COUNTER})
        number = cast(int, await tx.session.scalar(_NEXT, {"name": COUNTER}))
        child = cast(
            UUID,
            await tx.session.scalar(
                _CHILD,
                {
                    "t": tenant_id,
                    "agent": parent.agent_id,
                    "version": parent.spec_version,
                    "eng": parent.engagement_id,
                    "by": parent.initiator_user_id,
                    "scope": list(parent.task_scope or []),
                    "number": number,
                    "inputs": json.dumps({"plan": [dict(s) for s in steps]}, default=str),
                    "session": parent.session_id,
                    "parent": turn_run_id,
                    "clients": list(parent.client_scope or []),
                },
            ),
        )
        tx.record(
            "agent_run.started",
            target=Target("agent_run", child),
            after=Ref(initiator=parent.initiator_user_id, run_number=number),
            scope=Scope(engagement_id=parent.engagement_id),
        )
    return child
