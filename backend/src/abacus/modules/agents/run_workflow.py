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
Part 2 (P-10-T32, behind `workflow.patched("agent-run-v2-part-2")`): a question or an approval
step holds its branch `waiting_on_inputs` (the run `needs_input`), a decision step raises a C3
card and holds its branch `blocked` (the run `blocked_on_decision`); `question_answered` and
`decision_decided` wake the workflow, which reads each held step's rows (`wait_state`) and resumes
only that branch (AC-W4, AC-W5). `step_retry` runs a failed step again as a new row
(`retry_of_step_id`, AC-W6) and queues the steps its failure had skipped; `redirected` merges the
newest approved plan version (AC-W10); `stop` cancels what runs and what waits. A step activity
that fails after its retries fails its step only. A whole-run retry is a child run
(`run_commands.retry_run`). Histories: `agent-run-v2-{approved, question-answered,
question-skipped, decision-resumed, step-retried, stopped}.json` (`record_agent_run`).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Final

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from abacus.modules.agents.run_activities import PlanState, RunFacts, StepOutcome
    from abacus.modules.agents.run_waits import WaitState
    from abacus.modules.agents.run_plan import (
        PlanContext,
        PlanStep,
        Schedule,
        aggregate,
        cap,
        validate_plan,
    )

RUN_ID_PREFIX: Final = "agent_run:"
# P-10-T32: questions, decisions, retries, redirects and stop (ADR-090: `workflow.patched`).
PART_2: Final = "agent-run-v2-part-2"
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
        # Part 2 (P-10-T32): signals only wake the workflow; it reads the rows itself.
        self._woken = False
        self._stop = False
        self._redirected = False
        self._retries: list[str] = []

    @workflow.signal(name="question_answered")
    def question_answered(self) -> None:
        """P-10-T33's answer or skip route, after the person's row (AC-W5)."""
        self._woken = True

    @workflow.signal(name="decision_decided")
    def decision_decided(self) -> None:
        """`decision.decided` on a card a step is held on (`run_waits.on_decision_decided`)."""
        self._woken = True

    @workflow.signal(name="step_retry")
    def step_retry(self, step_key: str) -> None:
        """A person retried a failed step (AC-W6): it runs again as a new row."""
        self._retries.append(step_key)

    @workflow.signal(name="redirected")
    def redirected(self) -> None:
        """A redirect edited the plan (AC-W10): the newest approved version is read and merged."""
        self._redirected = True

    @workflow.signal(name="stop")
    def stop(self) -> None:
        """A person stopped the run: nothing new starts and the run ends cancelled."""
        self._stop = True

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
        blocked: dict[str, Any] | None = None,  # Any: JSON facts (the converter decodes Any)
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
        part2 = workflow.patched(PART_2)
        schedule = Schedule(steps, cap(facts.max_parallel))
        seq_of = {s.key: i for i, s in enumerate(steps, start=1)}
        next_seq = len(steps) + 1
        running: dict[str, asyncio.Task[StepOutcome]] = {}
        retried: dict[str, int] = {}  # a retried step's failed seq, for its new row
        paused = False
        while not schedule.done:
            if part2 and self._stop:
                return await self._stopped(p, schedule, running)
            if part2 and self._redirected:
                self._redirected = False
                plan = await self._act(
                    "agents.run_v2.plan_state", p.tenant_id, p.run_id, result_type=PlanState
                )
                if plan.state in ("approved", "standing"):
                    schedule.replace([PlanStep.parse(s) for s in plan.steps])
                    for s in schedule.steps:
                        if s.key not in seq_of:
                            seq_of[s.key] = next_seq
                            next_seq += 1
            if part2 and self._retries:
                for key in self._retries:
                    failed_seq = seq_of.get(key)
                    if failed_seq is not None and schedule.retry(key):
                        retried[key] = failed_seq
                        seq_of[key] = next_seq
                        next_seq += 1
                self._retries.clear()
            paused = await self._act(
                "agents.run_v2.paused", p.tenant_id, facts.engagement_id, result_type=bool
            )
            for step in schedule.start(paused=paused):
                retry_of = retried.pop(step.key, None)
                running[step.key] = asyncio.ensure_future(
                    workflow.execute_activity(
                        "agents.run_v2.execute_step",
                        args=[
                            p.tenant_id,
                            p.run_id,
                            seq_of[step.key],
                            step.dump(),
                            2 if retry_of is not None else 1,
                            retry_of,
                        ],
                        result_type=StepOutcome,
                        start_to_close_timeout=_STEP,
                        retry_policy=_STEP_RETRY,
                    )
                )
            if running:
                await self._state(p, "running")
                if part2:
                    await workflow.wait_condition(
                        lambda: any(t.done() for t in running.values()) or self._interrupted()
                    )
                else:
                    await workflow.wait(
                        list(running.values()), return_when=asyncio.FIRST_COMPLETED
                    )
                for key, task in list(running.items()):
                    if task.done():
                        schedule.finish(key, _outcome(task).state)
                        del running[key]
                continue
            if paused:
                await self._state(
                    p, "dispatched", "paused", {"kind": "capacity", "reason": "paused"}
                )
                await workflow.sleep(_PAUSE_POLL)
                continue
            if part2 and schedule.waiting:
                await self._held(p, schedule, seq_of)
                continue
            if part2 and (self._retries or self._redirected):
                continue
            if schedule.stalled:
                break  # nothing can start and no person is awaited: the run ends
        state = aggregate(schedule.states.values())
        terminal = state if state in ("succeeded", "failed", "cancelled") else "failed"
        return await self._end(p, terminal, None if terminal == "succeeded" else "steps_failed")

    def _interrupted(self) -> bool:
        return self._woken or self._stop or bool(self._retries) or self._redirected

    async def _held(self, p: AgentRunInput, schedule: Schedule, seq_of: dict[str, int]) -> None:
        """Part 2 (AC-W4, AC-W5): nothing runs and a branch waits on a person. The run shows why;
        a signal wakes it and each held step's rows say whether it moves on."""
        state = aggregate(schedule.states.values())
        held = schedule.waiting[0]
        kind = "question" if schedule.states[held] == "waiting_on_inputs" else "decision"
        await self._state(p, state, None, {"kind": kind, "step_seq": seq_of[held]})
        self._woken = False
        await workflow.wait_condition(self._interrupted)
        for key in list(schedule.waiting):
            step = next(s for s in schedule.steps if s.key == key)
            found = await self._act(
                "agents.run_v2.wait_state",
                p.tenant_id,
                p.run_id,
                seq_of[key],
                step.kind,
                result_type=WaitState,
            )
            if found.step_state is not None:
                schedule.finish(key, found.step_state)

    async def _stopped(
        self, p: AgentRunInput, schedule: Schedule, running: dict[str, asyncio.Task[StepOutcome]]
    ) -> str:
        """Stop (P-10-T33's route, a person's): running steps are cancelled at their activity,
        queued and held steps are cancelled, and the run ends `cancelled` with reason `stopped`."""
        for task in running.values():
            task.cancel()
        schedule.stop()
        await self._act("agents.run_v2.cancel_held", p.tenant_id, p.run_id, result_type=int)
        return await self._end(p, "cancelled", "stopped")

    async def _end(self, p: AgentRunInput, state: str, reason: str | None) -> str:
        await self._state(p, state, reason)
        await workflow.execute_activity(
            "agents.run_v2.complete",
            args=[p.tenant_id, p.run_id, state, reason],
            start_to_close_timeout=_SHORT,
            retry_policy=RetryPolicy(maximum_attempts=0, initial_interval=timedelta(seconds=5)),
        )
        return state


def _outcome(task: asyncio.Task[StepOutcome]) -> StepOutcome:
    """A finished step's outcome. The failure path (P-10-T32): an activity that failed after its
    retries, or was cancelled, fails its step only; independent branches carry on."""
    if task.cancelled():
        return StepOutcome("cancelled", "step_cancelled")
    error = task.exception()
    if error is not None:
        return StepOutcome("failed", "step_error")
    return task.result()
