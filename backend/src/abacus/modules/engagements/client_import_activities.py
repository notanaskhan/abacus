"""The worker's parts of CLI-06's bulk import (P-07-T52): `ClientImportWorkflow`'s activities and
the daily erase on its platform Schedule. The logic is `client_import`'s; these only adapt it.
"""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from temporalio import activity
from temporalio.exceptions import ApplicationError

from abacus.kernel.dispatch import PlatformSchedule, WorkClass, register_work_classes
from abacus.modules.engagements.client_import import (
    ImportNotRunnable,
    apply_import,
    complete_import,
    erase_files,
)
from abacus.modules.engagements.workflows import (
    CLIENT_IMPORT_ERASE_ID,
    ClientImportEraseWorkflow,
    ClientImportInput,
    ClientImportWorkflow,
)


@activity.defn(name="client_import.apply")
async def apply_activity(given: ClientImportInput) -> int:
    try:
        return await apply_import(
            UUID(given.tenant_id), UUID(given.import_id), heartbeat=activity.heartbeat
        )
    except ImportNotRunnable:
        raise ApplicationError(
            "the import can't run", type="ImportNotRunnable", non_retryable=True
        ) from None


@activity.defn(name="client_import.complete")
async def complete_activity(given: ClientImportInput) -> str:
    return await complete_import(UUID(given.tenant_id), UUID(given.import_id))


@activity.defn(name="client_import.mark_failed")
async def mark_failed_activity(given: ClientImportInput) -> str:
    return await complete_import(UUID(given.tenant_id), UUID(given.import_id), failed=True)


@activity.defn(name="client_import.erase_files")
async def erase_files_activity() -> int:
    return await erase_files()


WORKFLOWS: dict[type, WorkClass] = {
    ClientImportWorkflow: "batch",
    ClientImportEraseWorkflow: "background",
}
register_work_classes(WORKFLOWS)
ACTIVITIES: tuple[object, ...] = (
    apply_activity,
    complete_activity,
    mark_failed_activity,
    erase_files_activity,
)
SCHEDULES: tuple[PlatformSchedule, ...] = (
    PlatformSchedule(
        id=CLIENT_IMPORT_ERASE_ID,
        workflow=ClientImportEraseWorkflow,
        every=timedelta(days=1),
        note="P-07 OQ-4: bulk import files erased after 30 days (P-07-T52)",
    ),
)
