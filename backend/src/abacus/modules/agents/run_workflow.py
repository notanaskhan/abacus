"""`AgentRunWorkflow` part 1 (P-10-T29; SPEC-647 §3.4 AC-W1, AC-W3, AC-W8, §4.4; ADR-090, ADR-071,
ADR-005). PROTECTED (agents). Id `agent_run:<tenant>:<run>`; started only through
`kernel.dispatch` (DISPATCH-001).

create → plan (the run's deterministic plan; a model plan through the harness is P-10-T40's first
capability) → code validation (`run_plan.validate_plan`: a reserved action, an undeclared write, an
approver who lacks the action or a read outside `client_scope` fails the run `plan_invalid` before
approval, AC-W1) → `awaiting_plan_approval` (signal `plan_decided`, no timeout; the history is kept
short with continue-as-new) → DAG dispatch by level, at most `min(max_parallel_steps, 3)` steps at
once; a failed step skips only its dependants, independent branches carry on (AC-W3) → the
aggregate state → `complete`. Before each dispatch the workflow asks whether the firm's agents, the
engagement's agent or the `agent_runtime.v2` kill switch paused it; a pause stops new dispatches at
the step boundary and the run shows `blocked_on {kind: capacity, reason: paused}` (AC-W8).

Every transition is one `set_state` activity: the state, one `run_events` row on the run's own
sequence, one outbox event, one audit event. The workflow holds identifiers and codes only.
Questions, decisions, retries, redirects and stop are part 2 (P-10-T32), with their own
`workflow.patched` histories. Histories: `agent-run-v1-{approved, cancelled-at-plan}.json`.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Final

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from abacus.modules.agents.run_activities import PlanState, RunFacts, StepOutcome
    from abacus.modules.agents.run_plan import (
        PlanContext,
        PlanStep,
        Schedule,
        aggregate,
        cap,
        validate_plan,
    )

RUN_ID_PREFIX: Final = "agent_run:"
_SHORT = timedelta(seconds=30)
_STEP = timedelta(minutes=15)
_RETRY = RetryPolicy(maximum_attempts=5, initial_interval=timedelta(seconds=2))
# A step's activity retries only on infrastructure errors; a tool refusal is an outcome.
_STEP_RETRY = RetryPolicy(maximum_attempts=3, initial_interval=timedelta(seconds=5))
_PAUSE_POLL = timedelta(seconds=30)


@dataclass(frozen=True)
class AgentRunInput:
    tenant_id: str
    run_id: str
    # Carried across continue-as-new while the plan awaits a person (no client content).
    awaiting_version: int = 0
    signals: list[str] = field(default_factory=list[str])


@workflow.defn(name="AgentRunWorkflow")
class AgentRunWorkflow:
    def __init__(self) -> None:
        self._decided: str | None = None

    @workflow.signal(name="plan_decided")
    def plan_decided(self, decision: str) -> None:
        """P-10-T33's plan route, after a person's decision row: `approved`, `edited` or
        `cancelled`. The workflow reads the row itself; the signal only wakes it."""
        self._decided = decision

    async def _act[T](self, name: str, *args: object, result_type: type[T]) -> T:
        return await workflow.execute_activity(
            name,
            args=list(args),
            result_type=result_type,
            start_to_close_timeout=_SHORT,
            retry_policy=_RETRY,
        )

    async def _state(
        self,
        p: AgentRunInput,
        state: str,
        reason: str | None = None,
        blocked: dict[str, object] | None = None,
    ) -> None:
        await self._act(
            "agents.run_v2.set_state",
            p.tenant_id,
            p.run_id,
            state,
            reason,
            blocked,
            result_type=int,
        )

    @workflow.run
    async def run(self, p: AgentRunInput) -> str:
        facts = await self._act("agents.run_v2.load", p.tenant_id, p.run_id, result_type=RunFacts)
        version = p.awaiting_version
        if version == 0:
            await self._state(p, "planning")
            if facts.plan is None:
                return await self._end(p, "failed", "plan_unavailable")
            steps = [PlanStep.parse(s) for s in facts.plan]
            problems = validate_plan(
                steps,
                PlanContext(
                    declared_writes=frozenset(facts.declared_writes),
                    client_scope=frozenset(facts.client_scope),
                    approver_holds={pair: True for pair in facts.approver_holds},
                    tool_actions=facts.tool_actions,
                ),
            )
            version = await self._act(
                "agents.run_v2.record_plan",
                p.tenant_id,
                p.run_id,
                [s.dump() for s in steps],
                problems,
                result_type=int,
            )
            if version == 0:
                return await self._end(p, "failed", "plan_invalid")
            await self._state(p, "awaiting_plan_approval")
        await workflow.wait_condition(
            lambda: self._decided is not None or workflow.info().is_continue_as_new_suggested()
        )
        if self._decided is None:
            workflow.continue_as_new(AgentRunInput(p.tenant_id, p.run_id, version))
        plan = await self._act(
            "agents.run_v2.plan_state", p.tenant_id, p.run_id, result_type=PlanState
        )
        if plan.state == "cancelled":
            return await self._end(p, "cancelled", "plan_cancelled")
        if plan.state not in ("approved", "standing"):
            # A signal without a decided row (or an edit awaiting approval): wait again.
            self._decided = None
            workflow.continue_as_new(AgentRunInput(p.tenant_id, p.run_id, plan.version))
        await self._state(p, "dispatched")
        return await self._dispatch(p, facts, [PlanStep.parse(s) for s in plan.steps])

    async def _dispatch(self, p: AgentRunInput, facts: RunFacts, steps: list[PlanStep]) -> str:
        schedule = Schedule(steps, cap(facts.max_parallel))
        seq_of = {s.key: i for i, s in enumerate(steps, start=1)}
        running: dict[str, asyncio.Task[StepOutcome]] = {}
        paused = False
        while not schedule.done:
            paused = await self._act(
                "agents.run_v2.paused", p.tenant_id, facts.engagement_id, result_type=bool
            )
            for step in schedule.start(paused=paused):
                running[step.key] = asyncio.ensure_future(
                    workflow.execute_activity(
                        "agents.run_v2.execute_step",
                        args=[p.tenant_id, p.run_id, seq_of[step.key], step.dump()],
                        result_type=StepOutcome,
                        start_to_close_timeout=_STEP,
                        retry_policy=_STEP_RETRY,
                    )
                )
            if running:
                await self._state(p, "running")
                done, _ = await workflow.wait(
                    list(running.values()), return_when=asyncio.FIRST_COMPLETED
                )
                for key, task in list(running.items()):
                    if task in done:
                        outcome = task.result()
                        schedule.finish(key, outcome.state)
                        del running[key]
                continue
            if paused:
                await self._state(
                    p, "dispatched", "paused", {"kind": "capacity", "reason": "paused"}
                )
                await workflow.sleep(_PAUSE_POLL)
                continue
            if schedule.stalled:
                break  # nothing can start: P-10-T32's waits; part 1 ends the run here
        state = aggregate(schedule.states.values())
        terminal = state if state in ("succeeded", "failed", "cancelled") else "failed"
        return await self._end(p, terminal, None if terminal == "succeeded" else "steps_failed")

    async def _end(self, p: AgentRunInput, state: str, reason: str | None) -> str:
        await self._state(p, state, reason)
        await workflow.execute_activity(
            "agents.run_v2.complete",
            args=[p.tenant_id, p.run_id, state, reason],
            start_to_close_timeout=_SHORT,
            retry_policy=RetryPolicy(maximum_attempts=0, initial_interval=timedelta(seconds=5)),
        )
        return state
