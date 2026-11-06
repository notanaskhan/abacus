"""The due-soon half of TaxCalendarSweep (T-03-T07; T-03 §3 F5; DEC-2350), on a daily platform
Schedule. The date half runs on `reference_set.published` (`extensions.recompute_open_lines`)."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

from temporalio import activity, workflow
from temporalio.common import RetryPolicy

from abacus.kernel.dispatch import PlatformSchedule, WorkClass, register_work_classes

DUE_SOON_ID: Final = "tax_estimates_due_soon:platform"
_TIMEOUT: Final = timedelta(minutes=10)
_RETRY: Final = RetryPolicy(maximum_attempts=3)


@workflow.defn(name="TaxCalendarSweepWorkflow")
class TaxCalendarSweepWorkflow:
    """Started only by its Schedule (overlap SKIP); the event's key makes a repeat harmless."""

    @workflow.run
    async def run(self) -> int:
        return await workflow.execute_activity(
            "tax_estimates.send_due_soon",
            result_type=int,
            start_to_close_timeout=_TIMEOUT,
            retry_policy=_RETRY,
        )


@activity.defn(name="tax_estimates.send_due_soon")
async def send_due_soon_activity() -> int:
    from abacus.modules.tax.estimates import send_due_soon_all

    return await send_due_soon_all()


WORKFLOWS: dict[type, WorkClass] = {TaxCalendarSweepWorkflow: "background"}
register_work_classes(WORKFLOWS)
ACTIVITIES: tuple[object, ...] = (send_due_soon_activity,)
SCHEDULES: tuple[PlatformSchedule, ...] = (
    PlatformSchedule(
        id=DUE_SOON_ID,
        workflow=TaxCalendarSweepWorkflow,
        every=timedelta(days=1),
        note="T-03-T07: estimated-tax installments due within the week tell the return's team",
    ),
)
