"""Starting workflows: the only way (ADR-071; SPEC-003; TASK-018 design §2). PROTECTED.

    await dispatch(RetrievalWorkflow, RetrievalInput(...), id=workflow_id(run_id), ...)

Every workflow has a work class, which picks its task queue (`<base>-<class>`): interactive,
time-sensitive, background or batch, each served by its own worker pool, so bulk work never
delays a person waiting on a result. Modules declare their workflows' classes in their `api.py`
(`WORKFLOWS = {RetrievalWorkflow: "interactive"}`) and register them here at import
(`register_work_classes`); the kernel never imports a module. A workflow without a class can't be
registered or started. Its activities run on the workflow's queue (Temporal's default).
DISPATCH-001: nothing else starts a workflow or names a task queue.

Platform jobs run on Temporal Schedules (Q-01-T26; Q-01 §4.5): `schedule()` creates one, or
converges an existing one on the declared action, interval and policy while keeping its paused
state; `pause()`, `unpause()` and `delete()` are the operator's levers. Every Schedule skips a run
while the previous one is still open (overlap SKIP) and catches up at most one hour of missed
runs. Platform jobs only: firm-facing agent schedules (P-50) are a later decision on the same
primitive. Modules declare their Schedules in `api.py` (`SCHEDULES`); `abacus_tools.schedules`
ensures them, so no worker process races another to create one.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from typing import Final, Literal

from temporalio.client import (
    Schedule,
    ScheduleActionStartWorkflow,
    ScheduleAlreadyRunningError,
    ScheduleIntervalSpec,
    ScheduleOverlapPolicy,
    SchedulePolicy,
    ScheduleSpec,
    ScheduleState,
    ScheduleUpdate,
    ScheduleUpdateInput,
)
from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy

from abacus.kernel.config import settings
from abacus.kernel.logging import get_logger
from abacus.kernel.temporal import temporal_client
from abacus.kernel.work_class import WORK_CLASSES, WorkClass

_classes: dict[type, WorkClass] = {}
_log = get_logger(__name__)


def queue_for(work_class: WorkClass) -> str:
    """The task queue of a work class: `<base>-interactive`, `<base>-time-sensitive`, ..."""
    if work_class not in WORK_CLASSES:
        raise ValueError(f"unknown work class {work_class!r}")
    return f"{settings().temporal_task_queue}-{work_class.replace('_', '-')}"


def work_class_of_queue(task_queue: str) -> WorkClass | None:
    """The work class a task queue serves; None for the legacy single queue (or any other)."""
    for work_class in WORK_CLASSES:
        if task_queue == queue_for(work_class):
            return work_class
    return None


def register_work_classes(workflows: Mapping[type, WorkClass]) -> None:
    """Declare workflows' classes (each module's `WORKFLOWS`, at import). A workflow is
    registered once; registering it again with another class is a programming error."""
    for workflow, work_class in workflows.items():
        if work_class not in WORK_CLASSES:
            raise ValueError(f"{workflow.__name__}: unknown work class {work_class!r}")
        known = _classes.get(workflow)
        if known is not None and known != work_class:
            raise ValueError(f"{workflow.__name__} is already registered as {known!r}")
        _classes[workflow] = work_class


def work_class_of(workflow: type) -> WorkClass:
    found = _classes.get(workflow)
    if found is None:
        raise LookupError(f"{workflow.__name__} has no work class: register it (ADR-071)")
    return found


async def dispatch(
    workflow: type,
    arg: object,
    *,
    id: str,
    id_reuse_policy: WorkflowIDReusePolicy,
    id_conflict_policy: WorkflowIDConflictPolicy,
    execution_timeout: timedelta | None = None,
) -> None:
    """Start `workflow` on its class's queue (or attach to the one running with `id`, per the
    policies). The caller's trace continues into the workflow (kernel.temporal)."""
    work_class = work_class_of(workflow)
    client = await temporal_client()
    await client.start_workflow(
        workflow.run,  # pyright: ignore[reportUnknownArgumentType,reportUnknownMemberType] -- a @workflow.defn class
        arg,
        id=id,
        task_queue=queue_for(work_class),
        id_reuse_policy=id_reuse_policy,
        id_conflict_policy=id_conflict_policy,
        execution_timeout=execution_timeout,
    )
    _log.info("dispatch.started", workflow=workflow.__name__, work_class=work_class)


async def signal_with_start(
    workflow: type,
    arg: object,
    *,
    id: str,
    signal: str,
    payload: object,
) -> None:
    """Signal the long-lived workflow running with `id`, starting it first if none is (SPEC-027,
    ADR-062: an engagement's agent). The only way to signal a workflow (DISPATCH-001)."""
    work_class = work_class_of(workflow)
    client = await temporal_client()
    await client.start_workflow(
        workflow.run,  # pyright: ignore[reportUnknownArgumentType,reportUnknownMemberType] -- a @workflow.defn class
        arg,
        id=id,
        task_queue=queue_for(work_class),
        start_signal=signal,
        start_signal_args=[payload],
    )
    _log.info("dispatch.signalled", workflow=workflow.__name__, signal=signal)


# --- Schedules (Q-01-T26) -----------------------------------------------------------------------

# Chapter 03 §6: a missed run is caught up for at most an hour; an open run makes the next skip.
CATCHUP_WINDOW: Final = timedelta(hours=1)
OVERLAP: Final = ScheduleOverlapPolicy.SKIP


@dataclass(frozen=True)
class PlatformSchedule:
    """A platform job a module runs on a Schedule: `id` names both the Schedule and the runs it
    starts (Temporal suffixes each run's id with its time). The workflow takes no argument."""

    id: str
    workflow: type
    every: timedelta
    note: str


def _schedule_of(job: PlatformSchedule, *, state: ScheduleState) -> Schedule:
    work_class = work_class_of(job.workflow)
    return Schedule(
        action=ScheduleActionStartWorkflow(
            job.workflow.run,  # pyright: ignore[reportUnknownArgumentType,reportUnknownMemberType] -- a @workflow.defn class
            id=job.id,
            task_queue=queue_for(work_class),
        ),
        spec=ScheduleSpec(intervals=[ScheduleIntervalSpec(every=job.every)]),
        policy=SchedulePolicy(overlap=OVERLAP, catchup_window=CATCHUP_WINDOW),
        state=state,
    )


async def schedule(job: PlatformSchedule) -> Literal["created", "updated"]:
    """Create the Schedule, or converge an existing one on `job` (action, interval, policy). An
    operator's pause survives: the update keeps the Schedule's state as it is."""
    client = await temporal_client()
    try:
        await client.create_schedule(job.id, _schedule_of(job, state=ScheduleState(note=job.note)))
    except ScheduleAlreadyRunningError:

        def converge(given: ScheduleUpdateInput) -> ScheduleUpdate:
            return ScheduleUpdate(_schedule_of(job, state=given.description.schedule.state))

        await client.get_schedule_handle(job.id).update(converge)
        _log.info("dispatch.schedule_updated", schedule=job.id)
        return "updated"
    _log.info("dispatch.schedule_created", schedule=job.id)
    return "created"


async def pause(schedule_id: str, *, note: str) -> None:
    """Stop a Schedule starting runs (an open run carries on). `note` says who and why."""
    client = await temporal_client()
    await client.get_schedule_handle(schedule_id).pause(note=note)
    _log.info("dispatch.schedule_paused", schedule=schedule_id)


async def unpause(schedule_id: str, *, note: str) -> None:
    client = await temporal_client()
    await client.get_schedule_handle(schedule_id).unpause(note=note)
    _log.info("dispatch.schedule_unpaused", schedule=schedule_id)


async def delete(schedule_id: str) -> None:
    """Remove a Schedule (an open run carries on); `schedule()` creates it again."""
    client = await temporal_client()
    await client.get_schedule_handle(schedule_id).delete()
    _log.info("dispatch.schedule_deleted", schedule=schedule_id)


@dataclass(frozen=True)
class ScheduleFacts:
    """What an operator sees of a Schedule: no payload, no history."""

    id: str
    paused: bool
    note: str | None
    workflow_type: str
    task_queue: str
    every_seconds: tuple[int, ...]
    overlap: str
    catchup_window_seconds: int


async def describe_schedule(schedule_id: str) -> ScheduleFacts:
    client = await temporal_client()
    described = await client.get_schedule_handle(schedule_id).describe()
    given = described.schedule
    action = given.action
    if not isinstance(action, ScheduleActionStartWorkflow):
        raise LookupError(f"{schedule_id} does not start a workflow")
    return ScheduleFacts(
        id=schedule_id,
        paused=given.state.paused,
        note=given.state.note,
        workflow_type=str(action.workflow),
        task_queue=str(action.task_queue),
        every_seconds=tuple(int(i.every.total_seconds()) for i in given.spec.intervals),
        overlap=given.policy.overlap.name,
        catchup_window_seconds=int(given.policy.catchup_window.total_seconds()),
    )


__all__ = [
    "CATCHUP_WINDOW",
    "OVERLAP",
    "WORK_CLASSES",
    "PlatformSchedule",
    "ScheduleFacts",
    "WorkClass",
    "delete",
    "describe_schedule",
    "dispatch",
    "pause",
    "queue_for",
    "register_work_classes",
    "schedule",
    "signal_with_start",
    "unpause",
    "work_class_of",
    "work_class_of_queue",
]
