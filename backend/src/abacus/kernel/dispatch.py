"""Starting workflows: the only way (ADR-071; SPEC-003; TASK-018 design §2). PROTECTED.

    await dispatch(RetrievalWorkflow, RetrievalInput(...), id=workflow_id(run_id), ...)

Every workflow has a work class, which picks its task queue (`<base>-<class>`): interactive,
time-sensitive, background or batch, each served by its own worker pool, so bulk work never
delays a person waiting on a result. Modules declare their workflows' classes in their `api.py`
(`WORKFLOWS = {RetrievalWorkflow: "interactive"}`) and register them here at import
(`register_work_classes`); the kernel never imports a module. A workflow without a class can't be
registered or started. Its activities run on the workflow's queue (Temporal's default).
DISPATCH-001: nothing else starts a workflow or names a task queue.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
from typing import Final, Literal, get_args

from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy

from abacus.kernel.config import settings
from abacus.kernel.logging import get_logger
from abacus.kernel.temporal import temporal_client

WorkClass = Literal["interactive", "time_sensitive", "background", "batch"]
WORK_CLASSES: Final[tuple[WorkClass, ...]] = get_args(WorkClass)
_classes: dict[type, WorkClass] = {}
_log = get_logger(__name__)


def queue_for(work_class: WorkClass) -> str:
    """The task queue of a work class: `<base>-interactive`, `<base>-time-sensitive`, ..."""
    if work_class not in WORK_CLASSES:
        raise ValueError(f"unknown work class {work_class!r}")
    return f"{settings().temporal_task_queue}-{work_class.replace('_', '-')}"


def register_work_classes(workflows: Mapping[type, str]) -> None:
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
