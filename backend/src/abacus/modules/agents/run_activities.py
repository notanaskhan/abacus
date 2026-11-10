"""AgentRunWorkflow part 1's activities (P-10-T29; SPEC-647 §3.4, §4.4; ADR-090, ADR-071).
PROTECTED (agents).

Each activity proves what it acts on from the database (the run row under row-level security; the
agent's context through `identity.agent_context_for_run`, SYS-001), writes through the unit of
work, and returns identifiers and codes only, so no client content enters the workflow history.

- `agents.run_v2.load`: the run's facts the plan rules need (its pinned clients, the spec's
  declared writes, the parallel cap) and a deterministic plan when the run carries one
  (`inputs.plan`: an engagement plan or a test run). A model plan comes from the harness's
  `plan_proposed` output once a v2 capability is installable (P-10-T40); until then a run with no
  deterministic plan fails `plan_unavailable`.
- `agents.run_v2.record_plan`: the plan as a `proposed` version, or the run `failed` with
  `plan_invalid` and the codes when validation refused it (AC-W1).
- `agents.run_v2.plan_state`: the newest plan version's state, read after `plan_decided`; the
  decision row itself is written by P-10-T33's route, a person's (`require_live_human`).
- `agents.run_v2.set_state`: the run's state, reason and `blocked_on`, one `run_events` row (the
  run's own `event_seq`) and one outbox event per transition.
- `agents.run_v2.paused`: the firm's agents pause, the engagement's agent pause, or
  `agent_runtime.v2` turned off (the kill switch): checked before each dispatch (AC-W8).
- `agents.run_v2.execute_step`: one step row, and for a `tool` or `compute` step its one C17 call
  (`call_tool`, idempotency key `(run, seq, attempt)`). Questions, decisions, approvals and model
  steps are P-10-T32's: until then such a step fails `step_kind_pending`.
- `agents.run_v2.complete`: the terminal state and `finished_at`.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text
from temporalio import activity

from abacus.kernel._flags import AGENT_RUNTIME_V2
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.flags import flag_enabled
from abacus.kernel.uow import DomainEvent, Ref, Target, uow
from abacus.modules.agents.events import RunStateChanged
from abacus.modules.agents.tools.registry import registered_tools
from abacus.modules.agents.tools.runtime import ToolCallIn, call_tool
from abacus.modules.identity.api import (
    AgentContext,
    agent_context_for_run,
    agents_paused,
    engagement_resource,
    member_could,
)

_READER: Final = "agent-run-v2"


def _tenant(tenant_id: str, run_id: str) -> TenantContext:
    return TenantContext(UUID(tenant_id), "system", f"{_READER}:{run_id}")


@dataclass(frozen=True)
class RunFacts:
    state: str | None
    engagement_id: str | None
    client_scope: list[str]
    declared_writes: list[str]
    tool_actions: dict[str, str]
    max_parallel: int | None
    plan: list[dict[str, object]] | None
    approver_holds: list[tuple[str, str]] = field(default_factory=list[tuple[str, str]])


_RUN: Final = text(
    "SELECT r.state, r.engagement_id, r.client_scope, r.inputs, r.agent_id, r.task_scope "
    "FROM agent_runs r WHERE r.id = :run"
)


@activity.defn(name="agents.run_v2.load")
async def load_run_activity(tenant_id: str, run_id: str) -> RunFacts:
    async with tenant_session(_tenant(tenant_id, run_id)) as session:
        row = (await session.execute(_RUN, {"run": UUID(run_id)})).first()
    if row is None:
        raise ValueError("agent_run not found")
    inputs = cast(dict[str, object], row.inputs or {})
    raw_plan = inputs.get("plan")
    plan = cast(list[dict[str, object]], raw_plan) if isinstance(raw_plan, list) else None
    scope = set(cast(list[str], row.task_scope or []))
    tools = {n: t.action for n, t in registered_tools().items()}
    writes = sorted({t.action for t in registered_tools().values() if t.kind != "read"} & scope)
    holds = await _approver_holds(tenant_id, row.engagement_id, plan or [])
    parallel = inputs.get("max_parallel_steps")
    return RunFacts(
        state=row.state,
        engagement_id=str(row.engagement_id) if row.engagement_id else None,
        client_scope=[str(c) for c in cast(list[UUID], row.client_scope or [])],
        declared_writes=writes,
        tool_actions=tools,
        max_parallel=int(str(parallel)) if isinstance(parallel, int | str) else None,
        plan=plan,
        approver_holds=holds,
    )


async def _approver_holds(
    tenant_id: str, engagement_id: UUID | None, plan: list[dict[str, object]]
) -> list[tuple[str, str]]:
    """Which (approver, write) pairs a plan names that the approver may take now (AC-W1)."""
    if engagement_id is None:
        return []
    resource = await engagement_resource(_tenant(tenant_id, "plan"), engagement_id)
    held: list[tuple[str, str]] = []
    for step in plan:
        approver = step.get("approver_user_id")
        writes = step.get("writes")
        if not approver or not isinstance(writes, list):
            continue
        for write in cast(list[object], writes):
            action = str(write)
            if await member_could(UUID(tenant_id), UUID(str(approver)), action, resource):
                held.append((str(approver), action))
    return held


@activity.defn(name="agents.run_v2.record_plan")
async def record_plan_activity(
    tenant_id: str, run_id: str, steps: list[dict[str, object]], problems: list[str]
) -> int:
    """The plan as a `proposed` version (0 when refused: the run fails `plan_invalid`)."""
    tenant = _tenant(tenant_id, run_id)
    run = UUID(run_id)
    async with uow(tenant) as tx:
        if problems:
            tx.record(
                "agent_run.plan_refused",
                target=Target("agent_run", run),
                after=Ref(problems=len(problems), first=problems[0].split(":")[0]),
            )
            return 0
        version = cast(
            int,
            await tx.session.scalar(
                text(
                    "INSERT INTO agent_plans (tenant_id, run_id, version, steps, state) "
                    "SELECT :t, :run, coalesce(max(version), 0) + 1, CAST(:steps AS jsonb), "
                    "'proposed' FROM agent_plans WHERE run_id = :run RETURNING version"
                ),
                {"t": UUID(tenant_id), "run": run, "steps": json.dumps(steps)},
            ),
        )
        await tx.session.execute(
            text(
                "UPDATE agent_runs SET plan_id = (SELECT id FROM agent_plans WHERE run_id = :run "
                "AND version = :v) WHERE id = :run"
            ),
            {"run": run, "v": version},
        )
        tx.record(
            "agent_run.plan_proposed",
            target=Target("agent_run", run),
            after=Ref(version=version, steps=len(steps)),
        )
    return version


@dataclass(frozen=True)
class PlanState:
    version: int
    state: str  # proposed · approved · edited · cancelled · standing
    steps: list[dict[str, object]]


@activity.defn(name="agents.run_v2.plan_state")
async def plan_state_activity(tenant_id: str, run_id: str) -> PlanState:
    async with tenant_session(_tenant(tenant_id, run_id)) as session:
        row = (
            await session.execute(
                text(
                    "SELECT version, state, steps FROM agent_plans WHERE run_id = :run "
                    "ORDER BY version DESC LIMIT 1"
                ),
                {"run": UUID(run_id)},
            )
        ).first()
    if row is None:
        return PlanState(0, "missing", [])
    return PlanState(row.version, row.state, cast(list[dict[str, object]], row.steps or []))


@activity.defn(name="agents.run_v2.set_state")
async def set_state_activity(
    tenant_id: str,
    run_id: str,
    state: str,
    reason: str | None,
    blocked_on: dict[str, object] | None,
) -> int:
    """One transition: the state, its event (the run's own sequence) and its outbox event."""
    tenant = _tenant(tenant_id, run_id)
    run = UUID(run_id)
    async with uow(tenant) as tx:
        seq = cast(
            int,
            await tx.session.scalar(
                text(
                    "UPDATE agent_runs SET state = :state, state_reason = :reason, "
                    "blocked_on = CAST(:blocked AS jsonb), event_seq = event_seq + 1 "
                    "WHERE id = :run RETURNING event_seq"
                ),
                {
                    "state": state,
                    "reason": reason,
                    "blocked": json.dumps(blocked_on) if blocked_on is not None else None,
                    "run": run,
                },
            ),
        )
        await tx.session.execute(
            text(
                "INSERT INTO run_events (tenant_id, run_id, run_seq, type, payload) "
                "VALUES (:t, :run, :seq, 'run.state_changed', CAST(:payload AS jsonb))"
            ),
            {
                "t": UUID(tenant_id),
                "run": run,
                "seq": seq,
                "payload": json.dumps({"state": state, "reason": reason}),
            },
        )
        tx.record(
            "agent_run.state_changed",
            target=Target("agent_run", run),
            after=Ref(state=state, seq=seq),
        )
        event: DomainEvent = RunStateChanged(run_id=run, state=state, run_seq=seq)
        tx.emit(event)
    return seq


@activity.defn(name="agents.run_v2.paused")
async def paused_activity(tenant_id: str, engagement_id: str | None) -> bool:
    """AC-W8: the firm's pause, the engagement's agent pause, or the kill switch."""
    tenant = _tenant(tenant_id, "pause")
    if not await flag_enabled(tenant, AGENT_RUNTIME_V2, fresh=True):
        return True
    if await agents_paused(tenant) is not None:
        return True
    if engagement_id is None:
        return False
    async with tenant_session(tenant) as session:
        found = await session.scalar(
            text("SELECT paused_at IS NOT NULL FROM engagement_agents WHERE engagement_id = :e"),
            {"e": UUID(engagement_id)},
        )
    return bool(found)


@dataclass(frozen=True)
class StepOutcome:
    state: str  # succeeded · failed · skipped
    error_code: str | None = None
    records_read: int = 0
    active_ms: int = 0


async def _agent(tenant_id: str, run_id: str) -> AgentContext:
    async with tenant_session(_tenant(tenant_id, run_id)) as session:
        row = (
            await session.execute(
                text(
                    "SELECT agent_id, engagement_id, task_scope, initiator_user_id "
                    "FROM agent_runs WHERE id = :run"
                ),
                {"run": UUID(run_id)},
            )
        ).first()
    if row is None:
        raise ValueError("agent_run not found")
    return await agent_context_for_run(
        tenant_id=UUID(tenant_id),
        run_id=UUID(run_id),
        agent_id=row.agent_id,
        engagement_id=row.engagement_id,
        task_scope=frozenset(cast(list[str], row.task_scope or [])),
        initiator_user_id=row.initiator_user_id,
    )


def _args_hash(name: str, arguments: dict[str, object]) -> str:
    canonical = json.dumps({"name": name, "arguments": arguments}, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


@activity.defn(name="agents.run_v2.execute_step")
async def execute_step_activity(
    tenant_id: str, run_id: str, seq: int, step: dict[str, object], attempt: int = 1
) -> StepOutcome:
    """One step: its row, then (for a tool or compute step) its one C17 call."""
    tenant = _tenant(tenant_id, run_id)
    run = UUID(run_id)
    kind = str(step.get("kind", "tool"))
    tool_name = str(step["tool"]) if step.get("tool") else None
    arguments = cast(dict[str, object], step.get("arguments") or {})
    async with uow(tenant) as tx:
        step_id = cast(
            UUID,
            await tx.session.scalar(
                text(
                    "INSERT INTO agent_run_steps (tenant_id, run_id, seq, plan_step_key, level, "
                    "kind, tool_name, args_hash, state, started_at) VALUES (:t, :run, :seq, :key, "
                    ":level, :kind, :tool, :hash, 'running', clock_timestamp()) "
                    "ON CONFLICT (tenant_id, run_id, seq) DO UPDATE SET state = 'running' "
                    "RETURNING id"
                ),
                {
                    "t": UUID(tenant_id),
                    "run": run,
                    "seq": seq,
                    "key": str(step.get("key", ""))[:80],
                    "level": int(str(step.get("level", 0))),
                    "kind": kind,
                    "tool": tool_name,
                    "hash": _args_hash(tool_name or kind, arguments),
                },
            ),
        )
        tx.record("agent_run_step.started", target=Target("agent_run", run), after=Ref(seq=seq))
    if kind == "narration":
        outcome = StepOutcome("succeeded")
    elif kind in ("tool", "compute") and tool_name is not None:
        agent = await _agent(tenant_id, run_id)
        result = await call_tool(
            agent,
            ToolCallIn(
                run_id=run, step_seq=seq, attempt=attempt, name=tool_name, arguments=arguments
            ),
        )
        outcome = StepOutcome(
            "succeeded" if result.ok else "failed",
            None if result.ok else (result.code or "tool_failed"),
            result.records_read,
            result.active_ms,
        )
    else:
        outcome = StepOutcome("failed", "step_kind_pending")  # P-10-T32
    async with uow(tenant) as tx:
        await tx.session.execute(
            text(
                "UPDATE agent_run_steps SET state = :state, error_code = :code, "
                "records_read = :records, active_ms = :ms, ended_at = clock_timestamp() "
                "WHERE id = :id"
            ),
            {
                "state": outcome.state,
                "code": outcome.error_code,
                "records": outcome.records_read,
                "ms": outcome.active_ms,
                "id": step_id,
            },
        )
        await tx.session.execute(
            text(
                "UPDATE agent_runs SET records_read = records_read + :records, "
                "agent_ms = agent_ms + :ms WHERE id = :run"
            ),
            {"records": outcome.records_read, "ms": outcome.active_ms, "run": run},
        )
        tx.record(
            "agent_run_step.finished",
            target=Target("agent_run", run),
            after=Ref(seq=seq, state=outcome.state, code=outcome.error_code or "none"),
        )
    return outcome


@activity.defn(name="agents.run_v2.complete")
async def complete_run_activity(
    tenant_id: str, run_id: str, state: str, reason: str | None
) -> None:
    tenant = _tenant(tenant_id, run_id)
    run = UUID(run_id)
    async with uow(tenant) as tx:
        await tx.session.execute(
            text(
                "UPDATE agent_runs SET state = :state, state_reason = :reason, blocked_on = NULL, "
                "finished_at = coalesce(finished_at, clock_timestamp()) WHERE id = :run"
            ),
            {"state": state, "reason": reason, "run": run},
        )
        tx.record(
            "agent_run.completed_v2",
            target=Target("agent_run", run),
            after=Ref(state=state, reason=reason or "none"),
        )


RUN_V2_ACTIVITIES: Final = (
    load_run_activity,
    record_plan_activity,
    plan_state_activity,
    set_state_activity,
    paused_activity,
    execute_step_activity,
    complete_run_activity,
)
