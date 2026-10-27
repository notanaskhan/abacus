"""The engagements module's workflows (ADR-017, ADR-090). Orchestration only, activities by name.

`ClientImport` (P-07-T52; CLI-06 bulk import): `client_import:<tenant>:<import_id>` (reuse
rejected), started when a person runs an import. `client_import.apply` applies every row not yet
applied, each in its own unit of work and marked applied in it, so a retried activity or a
replayed history applies nothing twice; `client_import.complete` writes the counts and the
completion event. An apply that spends its retries ends in `client_import.mark_failed` (rows
already applied stay applied). A change to what it schedules goes behind `workflow.patched`, so
recorded histories keep replaying.

`ClientImportErase` runs `client_import.erase_files` daily on the platform Schedule
`client_import_erase:platform`: the uploaded files and sealed row TINs of imports past their 30
days are erased (P-07 OQ-4).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError

_APPLY_TIMEOUT = timedelta(minutes=30)
_APPLY_HEARTBEAT = timedelta(minutes=2)
_APPLY_RETRY = RetryPolicy(maximum_attempts=4, non_retryable_error_types=["ImportNotRunnable"])
_STAMP_TIMEOUT = timedelta(seconds=60)
_STAMP_RETRY = RetryPolicy(maximum_attempts=0)  # unlimited: the import never stays `importing`
_ERASE_TIMEOUT = timedelta(minutes=5)
_ERASE_RETRY = RetryPolicy(maximum_attempts=3)  # a missed day is erased by the next run

CLIENT_IMPORT_ERASE_ID = "client_import_erase:platform"


@dataclass(frozen=True)
class ClientImportInput:
    """By identifier only: every activity re-reads the import row."""

    tenant_id: str
    import_id: str


@workflow.defn(name="ClientImport")
class ClientImportWorkflow:
    @workflow.run
    async def run(self, given: ClientImportInput) -> str:
        try:
            await workflow.execute_activity(
                "client_import.apply",
                given,
                result_type=int,
                start_to_close_timeout=_APPLY_TIMEOUT,
                heartbeat_timeout=_APPLY_HEARTBEAT,
                retry_policy=_APPLY_RETRY,
            )
        except ActivityError:
            return await workflow.execute_activity(
                "client_import.mark_failed",
                given,
                result_type=str,
                start_to_close_timeout=_STAMP_TIMEOUT,
                retry_policy=_STAMP_RETRY,
            )
        return await workflow.execute_activity(
            "client_import.complete",
            given,
            result_type=str,
            start_to_close_timeout=_STAMP_TIMEOUT,
            retry_policy=_STAMP_RETRY,
        )


@workflow.defn(name="ClientImportErase")
class ClientImportEraseWorkflow:
    """Started only by its Schedule (overlap SKIP), so two workers never erase twice."""

    @workflow.run
    async def run(self) -> int:
        return await workflow.execute_activity(
            "client_import.erase_files",
            result_type=int,
            start_to_close_timeout=_ERASE_TIMEOUT,
            retry_policy=_ERASE_RETRY,
        )
