"""Destruction assembly on the platform schedule (Q-05-T11; S51 partials, TASK-8731; DEC-5725;
Q-05 §6 `DestructionAssembleWorkflow`). Dark behind `records.governance`.

The Schedule `destruction_assemble:platform` runs daily; the activity acts only on the first
business day after a quarter ends (US legal holidays from K-02's `legal_holidays` set, Central
time), then firm by firm with the flag on calls `destruction.assemble` with S3's observed
retain-until as the observer. `assemble` is once per quarter (the batch's ref), so a retried or
repeated run never makes a second batch. One firm's failure is logged by id and the others run.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Final, cast

from temporalio import activity

from abacus.kernel import calendar
from abacus.kernel._flags import RECORDS_GOVERNANCE
from abacus.kernel.clock import now as clock_now
from abacus.kernel.db import TenantContext
from abacus.kernel.dispatch import PlatformSchedule, WorkClass, register_work_classes
from abacus.kernel.flags import flag_enabled
from abacus.kernel.logging import get_logger
from abacus.modules.evidence.destruction_workflow import ACTIVITY, DestructionAssembleWorkflow

ASSEMBLE_ID: Final = "destruction_assemble:platform"
_QUARTER_STARTS: Final = (1, 4, 7, 10)
_log = get_logger(__name__)


def first_business_day_after_quarter_end(day: date, holidays: frozenset[date]) -> bool:
    """Whether `day` is the first business day of a quarter (the day after the last one ends)."""
    if day.month not in _QUARTER_STARTS:
        return False
    first, _ = calendar.roll(date(day.year, day.month, 1), holidays)
    return day == first


async def _holidays(around: date) -> frozenset[date]:
    from abacus.modules.platform.api import LegalHolidaysPayload, references_in_effect

    days: set[date] = set()
    for found in await references_in_effect("legal_holidays", around + timedelta(days=14)):
        days.update(row.date for row in cast(LegalHolidaysPayload, found.payload).rows)
    return frozenset(days)


async def assemble_due(at: datetime) -> int:
    """The sweep's body: the batches assembled at `at` (0 on any other day)."""
    from abacus.modules.evidence.destruction import CT, assemble
    from abacus.modules.evidence.storage import observed_retain_until
    from abacus.modules.identity.api import firm_tenant_ids

    local = at.astimezone(CT).date()
    if not first_business_day_after_quarter_end(local, await _holidays(local)):
        return 0
    made = 0
    for tenant_id in await firm_tenant_ids():
        if activity.in_activity():
            activity.heartbeat(str(tenant_id))
        tenant = TenantContext(tenant_id, "system", "destruction:assemble")
        try:
            if not await flag_enabled(tenant, RECORDS_GOVERNANCE):
                continue
            if await assemble(tenant_id, at, observed_retain_until) is not None:
                made += 1
        except Exception as exc:
            _log.error(
                "destruction_assemble.failed", tenant_id=str(tenant_id), error=type(exc).__name__
            )
    return made


@activity.defn(name=ACTIVITY)
async def assemble_sweep_activity() -> int:
    return await assemble_due((await clock_now()).astimezone(UTC))


WORKFLOWS: dict[type, WorkClass] = {DestructionAssembleWorkflow: "batch"}
register_work_classes(WORKFLOWS)
ACTIVITIES: tuple[object, ...] = (assemble_sweep_activity,)
SCHEDULES: tuple[PlatformSchedule, ...] = (
    PlatformSchedule(
        id=ASSEMBLE_ID,
        workflow=DestructionAssembleWorkflow,
        every=timedelta(days=1),
        note="Q-05-T11: the quarter's destruction batch, on the first business day after it ends",
    ),
)

__all__ = [
    "ACTIVITIES",
    "ASSEMBLE_ID",
    "SCHEDULES",
    "WORKFLOWS",
    "DestructionAssembleWorkflow",
    "assemble_due",
    "first_business_day_after_quarter_end",
]
