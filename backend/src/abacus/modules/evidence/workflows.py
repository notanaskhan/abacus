"""The upload processing workflow (SPEC-029; TASK-054; ADR-017, ADR-090, ADR-110). PROTECTED.

Orchestration only: activities by name, identifiers in, identifiers out. One run per upload
(`upload:<tenant>:<kind>:<id>`). TASK-055 (checks) and TASK-056 (previews) add steps behind
`workflow.patched(...)`; every history in `tests/workflows/histories/` must still replay.
Extraction never fails the run on a bad file: the activity records `unreadable` instead.
"""

from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from abacus.modules.evidence.workflow_types import VERSION, UploadInput

_TIMEOUT = timedelta(minutes=3)
_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=1),
    maximum_attempts=6,
)


@workflow.defn(name="upload_processing")
class UploadProcessing:
    @workflow.run
    async def run(self, given: UploadInput) -> str:
        status = await workflow.execute_activity(
            "upload.extract",
            given,
            result_type=str,
            start_to_close_timeout=_TIMEOUT,
            retry_policy=_RETRY,
        )
        # v2 (TASK-055): an evidence version is then checked; an inbox file waits until it's
        # assigned to an item (SPEC-029 Q8).
        if workflow.patched("checks") and given.kind == VERSION:
            await workflow.execute_activity(
                "upload.check",
                given,
                result_type=int,
                start_to_close_timeout=_TIMEOUT,
                retry_policy=_RETRY,
            )
        # v3 (TASK-056): previews, for versions and inbox files alike.
        if workflow.patched("previews"):
            await workflow.execute_activity(
                "upload.preview",
                given,
                result_type=str,
                start_to_close_timeout=_TIMEOUT,
                retry_policy=_RETRY,
            )
        return status
