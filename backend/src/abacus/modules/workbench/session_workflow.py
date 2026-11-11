"""`WorkbenchSessionWorkflow` (P-10-T43; SPEC-647 §3.7 AC-S1 to AC-S4; P-10 §4.4; ADR-090,
ADR-071; DEC-4301). Id `session:<tenant>:<session>`, interactive; started and signalled only
through `kernel.dispatch.signal_with_start` (DISPATCH-001).

Signals `user_message(seq)` and `answer([seq, question_seq])` name the person's item; the workflow
reads nothing else from them. Each is one turn, taken in arrival order from the side queue
(`SessionQueue`: a message typed while a question is open is answered first and the question
stays open, AC-S2). A turn is one activity (`workbench.session.turn`): the run's inline read-only
harness turn and its items. When the turn proposes writes, the activity has written exactly one
child run and the workflow starts that child's `AgentRunWorkflow` (abandoned on close, so the run
outlives the session's workflow), which waits in `awaiting_plan_approval` (AC-S4).

The workflow ends after an hour with nothing to do (the next post starts it again), or on
`close` once nothing waits, and keeps its
history short with continue-as-new, carrying the queue and the open question. Histories:
`session-v1-{read-only, child-run, side-queue}.json` (`record_session`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Final

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError

with workflow.unsafe.imports_passed_through():
    from abacus.modules.agents.api import AgentRunInput, run_workflow_id
    from abacus.modules.workbench.session_queue import SessionQueue, SessionWork

SESSION_ID_PREFIX: Final = "session:"
IDLE: Final = timedelta(hours=1)
_TURN = timedelta(minutes=10)
_RETRY = RetryPolicy(maximum_attempts=3, initial_interval=timedelta(seconds=2))


def session_workflow_id(tenant_id: str, session_id: str) -> str:
    return f"{SESSION_ID_PREFIX}{tenant_id}:{session_id}"


@dataclass(frozen=True)
class SessionInput:
    tenant_id: str
    session_id: str
    pending: list[SessionWork] = field(default_factory=list[SessionWork])
    open_question: int = 0


@dataclass(frozen=True)
class TurnDone:
    """The activity's answer: the question item it opened (0: none) and the child run it wrote."""

    asked: int = 0
    child_run_id: str | None = None


@workflow.defn(name="WorkbenchSessionWorkflow")
class WorkbenchSessionWorkflow:
    def __init__(self) -> None:
        self._queue = SessionQueue()
        self._closed = False

    @workflow.signal(name="close")
    def close(self) -> None:
        """The session was deleted (W-02) or retired: finish what waits, then end."""
        self._closed = True

    @workflow.signal(name="user_message")
    def user_message(self, seq: int) -> None:
        self._queue.message(seq)

    @workflow.signal(name="answer")
    def answer(self, ref: list[int]) -> None:
        """`[seq, question_seq]`: the answer's item and the question item it answers."""
        self._queue.answer(ref[0], ref[1])

    @workflow.run
    async def run(self, p: SessionInput) -> str:
        carried = SessionQueue.resume(p.pending, p.open_question)
        carried.pending.extend(self._queue.pending)  # signals that arrived with the start
        self._queue = carried
        while True:
            try:
                await workflow.wait_condition(
                    lambda: (
                        bool(self._queue.pending)
                        or self._closed
                        or workflow.info().is_continue_as_new_suggested()
                    ),
                    timeout=IDLE,
                )
            except TimeoutError:
                return "idle"
            if workflow.info().is_continue_as_new_suggested():
                pending, open_question = self._queue.snapshot()
                workflow.continue_as_new(
                    SessionInput(p.tenant_id, p.session_id, pending, open_question)
                )
            work = self._queue.take()
            if work is None:
                if self._closed:
                    return "closed"
                continue
            try:
                done = await workflow.execute_activity(
                    "workbench.session.turn",
                    args=[p.tenant_id, p.session_id, work.kind, work.seq],
                    result_type=TurnDone,
                    start_to_close_timeout=_TURN,
                    retry_policy=_RETRY,
                )
            except ActivityError:
                done = TurnDone()  # the turn's run failed; the session takes the next turn
            self._queue.turn_ended(work, done.asked)
            if done.child_run_id is not None:
                await self._start_child(p.tenant_id, done.child_run_id)

    async def _start_child(self, tenant_id: str, run_id: str) -> None:
        await workflow.start_child_workflow(
            "AgentRunWorkflow",
            AgentRunInput(tenant_id, run_id),
            id=run_workflow_id(tenant_id, run_id),
            parent_close_policy=workflow.ParentClosePolicy.ABANDON,
        )
