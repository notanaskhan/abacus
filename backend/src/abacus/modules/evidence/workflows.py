"""The upload processing workflow (SPEC-029; TASK-054; ADR-017, ADR-090, ADR-110). PROTECTED.

Orchestration only: activities by name, identifiers in, identifiers out. One run per upload
(`upload:<tenant>:<kind>:<id>`). TASK-055 (checks) and TASK-056 (previews) add steps behind
`workflow.patched(...)`; every history in `tests/workflows/histories/` must still replay. P-03-T05
adds v4 `words` (the word layer) and the `trust_layer_backfill` workflow.
Extraction never fails the run on a bad file: the activity records `unreadable` instead.
"""

from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from abacus.modules.evidence.workflow_types import VERSION, BackfillInput, UploadInput

_TIMEOUT = timedelta(minutes=3)
_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=1),
    maximum_attempts=6,
)
BACKFILL_BATCH = 50


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
        # v4 (P-03-T05): the word layer, for versions and inbox files alike.
        if workflow.patched("words"):
            await workflow.execute_activity(
                "upload.words",
                given,
                result_type=int,
                start_to_close_timeout=_TIMEOUT,
                retry_policy=_RETRY,
            )
        return status


@workflow.defn(name="trust_layer_backfill")
class TrustLayerBackfill:
    """P-03 §4.5 (P-03-T05): one tenant's uploads that have no word layer get one, by the same
    activity as new uploads (idempotent). Batches of `BACKFILL_BATCH` by id cursor, so a file
    that yields no layer is passed, never retried forever; continues as new while a batch is
    full. Started by an operator command (`abacus_tools.trust_layer_backfill`)."""

    @workflow.run
    async def run(self, given: BackfillInput) -> int:
        batch = await workflow.execute_activity(
            "trust_layer.pending_words",
            given,
            result_type=list[UploadInput],
            start_to_close_timeout=_TIMEOUT,
            retry_policy=_RETRY,
        )
        for upload in batch:
            await workflow.execute_activity(
                "upload.words",
                upload,
                result_type=int,
                start_to_close_timeout=_TIMEOUT,
                retry_policy=_RETRY,
            )
        versions = [u.source_id for u in batch if u.kind == VERSION]
        inbox = [u.source_id for u in batch if u.kind != VERSION]
        reached = BackfillInput(
            given.tenant_id,
            versions[-1] if versions else given.after_version,
            inbox[-1] if inbox else given.after_inbox,
            given.done + len(batch),
        )
        if len(batch) >= BACKFILL_BATCH:
            workflow.continue_as_new(reached)
        return reached.done
