"""The synthetic-only run recorder (P-09-T07; P-09 §8.3: "a synthetic-only run-recording service
the scenario loader can call"; DEC-3004). PROTECTED (agents).

P-10's harness (P-10-T25, S33) is what records real v2 runs. Until then, and afterwards for the
Brightwater Hale scenario (P-09-T12: #4118, #4119, #4127, the Aug 17 failure, Copperleaf Run 2),
this writes a v2 run as the runtime would leave it: the run row with its v2 columns, one decided
plan version, a step row per plan step reached with its state and times, and its `item.appended`
run events in `run_seq` order. It refuses every firm that is not synthetic (`NotSynthetic`), so
nothing it writes can stand in for a real run's record.

The plan decision is a person's (0681's human-only check): the recorder writes as the run's
initiator, a human context, inside one unit of work with one audit event,
`agent_run.recorded_synthetic`.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Final, cast
from uuid import UUID, uuid4

from sqlalchemy import text

from abacus.kernel.db import TenantContext
from abacus.kernel.errors import DomainForbidden
from abacus.kernel.uow import Ref, Scope, Target, uow
from abacus.modules.agents.run_views import BUCKET, ITEM_KINDS
from abacus.modules.identity.api import is_synthetic_firm


class NotSynthetic(DomainForbidden):
    code = "synthetic_only"


@dataclass(frozen=True)
class RecordedStep:
    key: str
    level: int
    label: str
    state: str  # agent_run_steps.state
    kind: str = "tool"
    tool_name: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    needs: Sequence[str] = ()
    records_read: int = 0
    reached: bool = True  # False: in the plan, no step row yet (queued, no tool card)


@dataclass(frozen=True)
class RecordedItem:
    kind: str  # the C6 v2 wire set
    code: str
    at: datetime
    outcome: str | None = None
    detail: str | None = None
    ref_type: str | None = None
    ref_id: UUID | None = None
    blocks: Mapping[str, object] | None = None


@dataclass(frozen=True)
class RecordedRun:
    agent_id: str
    engagement_id: UUID
    initiator_user_id: UUID
    run_number: int
    state: str  # agent_runs.state (C2's 14 run states)
    steps: Sequence[RecordedStep]
    items: Sequence[RecordedItem] = ()
    state_reason: str | None = None
    blocked_on: Mapping[str, object] | None = None
    trigger_kind: str = "manual"
    work_item_ref: str | None = None
    task_scope: Sequence[str] = ()
    plan_decided_at: datetime | None = None
    counters: Mapping[str, int] = field(default_factory=dict[str, int])
    id: UUID = field(default_factory=uuid4)


_COUNTERS: Final = (
    "records_read",
    "citations_count",
    "writes_done",
    "writes_waiting",
    "agent_ms",
    "agent_minutes",
)
_RUN = text(
    "INSERT INTO agent_runs (id, tenant_id, agent_id, spec_version, engagement_id, "
    "initiator_user_id, task_scope, state, state_reason, blocked_on, run_number, mode, "
    "trigger_kind, work_item_ref, runs_as_user_id, test) VALUES (:id, :tenant, :agent, 2, "
    ":engagement, :initiator, :scope, :state, :reason, CAST(:blocked AS jsonb), :number, "
    "'run', :trigger, :work_item, :initiator, true)"
)
_PLAN = text(
    "INSERT INTO agent_plans (id, tenant_id, run_id, version, steps, state, decided_by, "
    "decided_at) VALUES (:id, :tenant, :run, 1, CAST(:steps AS jsonb), 'approved', :by, :at)"
)
_STEP = text(
    "INSERT INTO agent_run_steps (id, tenant_id, run_id, seq, plan_step_key, level, kind, "
    "tool_name, state, needs) VALUES (:id, :tenant, :run, :seq, :key, :level, :kind, :tool, "
    ":state, CAST(:needs AS jsonb))"
)
_STEP_TIMES = text(
    "UPDATE agent_run_steps SET started_at = :started, ended_at = :ended, "
    "records_read = :records WHERE id = :id"
)
_EVENT = text(
    "INSERT INTO run_events (tenant_id, run_id, run_seq, type, payload) VALUES "
    "(:tenant, :run, :seq, 'item.appended', CAST(:payload AS jsonb))"
)
_FINISH = text(
    "UPDATE agent_runs SET plan_id = :plan, event_seq = :seq, records_read = :records_read, "
    "citations_count = :citations_count, writes_done = :writes_done, "
    "writes_waiting = :writes_waiting, agent_ms = :agent_ms, agent_minutes = :agent_minutes "
    "WHERE id = :run"
)


def _check(run: RecordedRun) -> None:
    keys = [s.key for s in run.steps]
    if len(set(keys)) != len(keys):
        raise ValueError("a plan step key is recorded once")
    for step in run.steps:
        if step.state not in BUCKET:
            raise ValueError(f"unknown step state {step.state!r}")
    for item in run.items:
        if item.kind not in ITEM_KINDS:
            raise ValueError(f"unknown item kind {item.kind!r}")
    unknown = set(run.counters) - set(_COUNTERS)
    if unknown:
        raise ValueError(f"unknown counters {sorted(unknown)}")


async def record_synthetic_run(tenant: TenantContext, run: RecordedRun) -> UUID:
    """Record `run` for a synthetic firm (module docstring). `tenant` is the initiator's."""
    _check(run)
    if tenant.actor_kind != "human" or tenant.actor_id != str(run.initiator_user_id):
        raise ValueError("the recorder writes as the run's initiator")
    if not await is_synthetic_firm(tenant):
        raise NotSynthetic
    plan_id = uuid4()
    plan = [{"key": s.key, "label": s.label, "level": s.level} for s in run.steps]
    async with uow(tenant) as tx:
        await tx.session.execute(
            _RUN,
            {
                "id": run.id,
                "tenant": tenant.tenant_id,
                "agent": run.agent_id,
                "engagement": run.engagement_id,
                "initiator": run.initiator_user_id,
                "scope": list(run.task_scope),
                "state": run.state,
                "reason": run.state_reason,
                "blocked": None if run.blocked_on is None else json.dumps(dict(run.blocked_on)),
                "number": run.run_number,
                "trigger": run.trigger_kind,
                "work_item": run.work_item_ref,
            },
        )
        await tx.session.execute(
            _PLAN,
            {
                "id": plan_id,
                "tenant": tenant.tenant_id,
                "run": run.id,
                "steps": json.dumps(plan),
                "by": run.initiator_user_id,
                "at": run.plan_decided_at,
            },
        )
        seq = 0
        for step in run.steps:
            if not step.reached:
                continue
            seq += 1
            step_id = uuid4()
            await tx.session.execute(
                _STEP,
                {
                    "id": step_id,
                    "tenant": tenant.tenant_id,
                    "run": run.id,
                    "seq": seq,
                    "key": step.key,
                    "level": step.level,
                    "kind": step.kind,
                    "tool": step.tool_name,
                    "state": step.state,
                    "needs": json.dumps(list(step.needs)) if step.needs else None,
                },
            )
            await tx.session.execute(
                _STEP_TIMES,
                {
                    "id": step_id,
                    "started": step.started_at,
                    "ended": step.ended_at,
                    "records": step.records_read,
                },
            )
        for n, item in enumerate(sorted(run.items, key=lambda i: i.at), start=1):
            payload = {
                "kind": item.kind,
                "code": item.code,
                "at": item.at.isoformat(),
                "outcome": item.outcome,
                "detail": item.detail,
                "ref_type": item.ref_type,
                "ref_id": None if item.ref_id is None else str(item.ref_id),
                "blocks": None if item.blocks is None else dict(item.blocks),
            }
            await tx.session.execute(
                _EVENT,
                {
                    "tenant": tenant.tenant_id,
                    "run": run.id,
                    "seq": n,
                    "payload": json.dumps(payload),
                },
            )
        counters = {c: int(run.counters.get(c, 0)) for c in _COUNTERS}
        await tx.session.execute(
            _FINISH, {"plan": plan_id, "seq": len(run.items) or None, "run": run.id, **counters}
        )
        tx.record(
            "agent_run.recorded_synthetic",
            target=Target("agent_run", run.id),
            after=Ref(run_number=run.run_number, plan=plan_id),
            scope=Scope(engagement_id=run.engagement_id),
        )
    return run.id


_STEP_OF = text(
    "SELECT id, state FROM agent_run_steps WHERE run_id = :run AND plan_step_key = :key "
    "ORDER BY seq DESC LIMIT 1"
)
_STEP_STATE = text(
    "UPDATE agent_run_steps SET state = :state, ended_at = :ended, error_code = :error "
    "WHERE id = :id"
)
_RUN_STATE = text(
    "UPDATE agent_runs SET state = :state, blocked_on = CAST(:blocked AS jsonb), "
    "event_seq = event_seq + 1 WHERE id = :run RETURNING event_seq"
)
_STATE_EVENT = text(
    "INSERT INTO run_events (tenant_id, run_id, run_seq, type, payload) VALUES "
    "(:tenant, :run, :seq, 'step.state', CAST(:payload AS jsonb))"
)


@dataclass(frozen=True)
class StepAdvance:
    """A recorded step's later state, at the scenario's business time (P-10-T36)."""

    run_id: UUID
    key: str
    state: str  # agent_run_steps.state
    at: datetime
    run_state: str  # the run's state after it (C2's 14)
    blocked_on: Mapping[str, object] | None = None
    error_code: str | None = None


async def advance_synthetic_step(tenant: TenantContext, advance: StepAdvance) -> int:
    """P-10-T36: move one recorded step on (#4127's internal control failing at 9:58, Margaret
    Okonkwo's decision releasing materiality at 11:12), its run's state and one `step.state`
    run event, for a synthetic firm only. Returns the run's new event sequence."""
    if advance.state not in BUCKET:
        raise ValueError(f"unknown step state {advance.state!r}")
    if tenant.actor_kind != "human":
        raise ValueError("the recorder writes as a person of the scenario")
    if not await is_synthetic_firm(tenant):
        raise NotSynthetic
    async with uow(tenant) as tx:
        step = (
            await tx.session.execute(_STEP_OF, {"run": advance.run_id, "key": advance.key})
        ).first()
        if step is None:
            raise ValueError(f"step {advance.key!r} was not reached")
        ended = (
            advance.at
            if advance.state in ("succeeded", "failed", "skipped", "cancelled")
            else None
        )
        await tx.session.execute(
            _STEP_STATE,
            {"id": step.id, "state": advance.state, "ended": ended, "error": advance.error_code},
        )
        seq = int(
            await tx.session.scalar(
                _RUN_STATE,
                {
                    "state": advance.run_state,
                    "blocked": None
                    if advance.blocked_on is None
                    else json.dumps(dict(advance.blocked_on)),
                    "run": advance.run_id,
                },
            )
            or 0
        )
        await tx.session.execute(
            _STATE_EVENT,
            {
                "tenant": tenant.tenant_id,
                "run": advance.run_id,
                "seq": seq,
                "payload": json.dumps(
                    {
                        "step_id": str(step.id),
                        "state": advance.state,
                        "at": advance.at.isoformat(),
                        "error_code": advance.error_code,
                    }
                ),
            },
        )
        tx.record(
            "agent_run.advanced_synthetic",
            target=Target("agent_run", advance.run_id),
            after=Ref(step=cast(UUID, step.id), seq=seq),
        )
    return seq


__all__ = [
    "NotSynthetic",
    "RecordedItem",
    "RecordedRun",
    "RecordedStep",
    "StepAdvance",
    "advance_synthetic_step",
    "record_synthetic_run",
]
