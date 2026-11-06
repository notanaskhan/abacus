"""TaxCalendarSweep's worker parts (T-03-T07; DEC-2350): its activity, class and Schedule."""

from __future__ import annotations

from datetime import timedelta

from temporalio import activity

from abacus.kernel.dispatch import PlatformSchedule, WorkClass, register_work_classes
from abacus.modules.tax.schedule_workflows import DUE_SOON_ID, TaxCalendarSweepWorkflow


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
