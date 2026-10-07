"""Worker metrics (ADR-094; SPEC-003 AC-15; TASK-018 design §7).

`ScheduleToStartInterceptor` records how long each activity waited on its task queue, by work
class: the latency each worker pool's sizing is judged by (ADR-071). The legacy single queue is
reported as `legacy`.
"""

from __future__ import annotations

from typing import Final

from opentelemetry.metrics import Histogram
from temporalio import activity
from temporalio.worker import ActivityInboundInterceptor, ExecuteActivityInput, Interceptor

from abacus.kernel.dispatch import work_class_of_queue
from abacus.kernel.metrics import meter

SCHEDULE_TO_START: Final = "abacus.schedule_to_start"
_histogram: Histogram | None = None


def _schedule_to_start() -> Histogram:
    global _histogram
    if _histogram is None:
        _histogram = meter(__name__).create_histogram(
            SCHEDULE_TO_START,
            unit="s",
            description="Time an activity waited on its task queue before a worker started it",
        )
    return _histogram


class _ScheduleToStartInbound(ActivityInboundInterceptor):
    async def execute_activity(self, input: ExecuteActivityInput) -> object:
        info = activity.info()
        waited = (info.started_time - info.current_attempt_scheduled_time).total_seconds()
        work_class = work_class_of_queue(info.task_queue) or "legacy"
        _schedule_to_start().record(max(waited, 0.0), {"work_class": work_class})
        return await super().execute_activity(input)


class ScheduleToStartInterceptor(Interceptor):
    """Worker interceptor: record each activity's schedule-to-start latency by work class."""

    def intercept_activity(self, next: ActivityInboundInterceptor) -> ActivityInboundInterceptor:
        return _ScheduleToStartInbound(next)
