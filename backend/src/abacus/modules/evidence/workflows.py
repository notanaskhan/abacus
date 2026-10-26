"""The upload processing workflow (SPEC-029; TASK-054; ADR-017, ADR-090, ADR-110). PROTECTED.

Orchestration only: activities by name, identifiers in, identifiers out. One run per upload
(`upload:<tenant>:<kind>:<id>`). TASK-055 (checks) and TASK-056 (previews) add steps behind
`workflow.patched(...)`; every history in `tests/workflows/histories/` must still replay.
P-03-T05 adds v4 `words` (the word layer) and the `trust_layer_backfill` workflow; P-03-T13
adds v5 `pii_scan`; R-01-T09 v6 `portal_drop_sort`; P-03-T15 v7 `masked_preview`, which
replaces the unmasked v3 preview for new runs, and the backfill's v2 `masks`. The legal-hold
workflows (Q-02-T29) follow the upload workflow, with their own v1 histories. The engagement
export (A-01-T19) is v1, recorded in its own histories.
Extraction never fails the run on a bad file: the activity records `unreadable` instead.
"""

from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError

with workflow.unsafe.imports_passed_through():
    from abacus.modules.evidence.workflow_types import (
        BUILD_ERROR,
        HOLD_NOT_FOUND,
        INBOX,
        INTEGRITY_MISMATCH,
        SECTION_MISSING,
        VERSION,
        BackfillInput,
        EngagementExportInput,
        ExportFailure,
        ExportPackageFacts,
        LegalHoldInput,
        UploadInput,
        WithdrawalPurgeInput,
    )

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
        # v3 (TASK-056): previews, for versions and inbox files alike. From v7 (P-03-T15) a run
        # never makes an unmasked rendition: the masked one below replaces it.
        if workflow.patched("previews") and not workflow.patched("masked_preview"):
            await workflow.execute_activity(
                "upload.preview",
                given,
                result_type=str,
                start_to_close_timeout=_TIMEOUT,
                retry_policy=_RETRY,
            )
        # v4 (P-03-T05): the word layer, for versions and inbox files alike. A layer that can't
        # be built never undoes the steps before it; the backfill tries the upload again.
        if workflow.patched("words"):
            try:
                await workflow.execute_activity(
                    "upload.words",
                    given,
                    result_type=int,
                    start_to_close_timeout=_TIMEOUT,
                    retry_policy=_RETRY,
                )
            except ActivityError:
                workflow.logger.warning("upload.words_failed", extra={"kind": given.kind})
        # v5 (P-03-T13): PII detection over the word layer. A scan that can't run never undoes
        # the steps before it. Until a scan lists a page, the word-layer readers (quotes,
        # search, relink) and a portal drop's matcher never read it; other agent material
        # still comes from the extraction until P-03-T15 masks it (DEC-322).
        if workflow.patched("pii_scan"):
            try:
                await workflow.execute_activity(
                    "upload.pii_scan",
                    given,
                    result_type=int,
                    start_to_close_timeout=_TIMEOUT,
                    retry_policy=_RETRY,
                )
            except ActivityError:
                workflow.logger.warning("upload.pii_scan_failed", extra={"kind": given.kind})
        # v7 (P-03-T15): the masked rendition, after the scan it masks from. One that can't be
        # made never undoes the steps before it; the backfill makes it later. Until then no page
        # is served (409 `preview_outdated` or 404), never an unmasked one.
        if workflow.patched("masked_preview"):
            try:
                await workflow.execute_activity(
                    "upload.masked_preview",
                    given,
                    result_type=str,
                    start_to_close_timeout=_TIMEOUT,
                    retry_policy=_RETRY,
                )
            except ActivityError:
                workflow.logger.warning("upload.masked_preview_failed", extra={"kind": given.kind})
        # v6 (R-01-T09): a portal drop is sorted by the code rule, after its extraction. Any other
        # inbox file answers `not_a_drop`; a sort that fails for good leaves the file waiting for
        # a person in the inbox, as it would be unsorted.
        if workflow.patched("portal_drop_sort") and given.kind == INBOX:
            try:
                await workflow.execute_activity(
                    "upload.portal_drop_sort",
                    given,
                    result_type=str,
                    start_to_close_timeout=_TIMEOUT,
                    retry_policy=_RETRY,
                )
            except ActivityError:
                workflow.logger.warning("upload.portal_drop_sort_failed")
        return status


# --- Withdrawal purge (P-06-T19; ADR-162 §7). v1, recorded in its history. --------------------

# An erase attempt must end up done or retried whatever the outage: retry without limit.
_PURGE_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=5),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=10),
    maximum_attempts=0,
)
PURGE_ATTEMPTS_PER_RUN = 30  # then continue as new, so a long hold never grows the history


@workflow.defn(name="evidence_withdrawal_purge")
class EvidenceWithdrawalPurge:
    """`withdrawal:<tenant>:<version>`: sleep through the window on a durable timer, then ask the
    erase activity, which checks the business clock and the legal holds and answers 0 when the
    key is destroyed (or nothing is left to do), else how many seconds to wait: the rest of the
    window, or a day while held or while no hold check is registered (fail closed)."""

    @workflow.run
    async def run(self, given: WithdrawalPurgeInput) -> int:
        wait, attempts = given.wait_seconds, given.attempts
        while True:
            if wait > 0:
                await workflow.sleep(timedelta(seconds=wait))
            wait = await workflow.execute_activity(
                "evidence_withdrawal.erase",
                given,
                result_type=int,
                start_to_close_timeout=_TIMEOUT,
                retry_policy=_PURGE_RETRY,
            )
            attempts += 1
            if wait <= 0:
                return attempts
            if attempts - given.attempts >= PURGE_ATTEMPTS_PER_RUN:
                workflow.continue_as_new(
                    WithdrawalPurgeInput(
                        given.tenant_id, given.evidence_version_id, wait, attempts
                    )
                )


# --- Legal holds (Q-02-T29; Q-02 §4.5; ADR-033). v1 of both, recorded in histories. -----------

# A hold must end up set (or cleared) whatever the outage: retry without limit, backing off to
# five minutes. The hold check reads the database meanwhile, so nothing held can be erased.
_HOLD_TIMEOUT = timedelta(minutes=10)
_HOLD_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=5),
    maximum_attempts=0,
    non_retryable_error_types=[HOLD_NOT_FOUND],
)


@workflow.defn(name="legal_hold_apply")
class LegalHoldApply:
    """`legal_hold_apply:<tenant>:<hold>`: count every version in scope, set the S3 object legal
    hold on each in batches, then make the hold active."""

    @workflow.run
    async def run(self, given: LegalHoldInput) -> str:
        pending = await workflow.execute_activity(
            "legal_hold.apply_batch",
            given,
            result_type=int,
            start_to_close_timeout=_HOLD_TIMEOUT,
            retry_policy=_HOLD_RETRY,
        )
        while pending > 0:
            pending = await workflow.execute_activity(
                "legal_hold.apply_batch",
                given,
                result_type=int,
                start_to_close_timeout=_HOLD_TIMEOUT,
                retry_policy=_HOLD_RETRY,
            )
        return await workflow.execute_activity(
            "legal_hold.activate",
            given,
            result_type=str,
            start_to_close_timeout=_TIMEOUT,
            retry_policy=_HOLD_RETRY,
        )


@workflow.defn(name="legal_hold_release")
class LegalHoldRelease:
    """`legal_hold_release:<tenant>:<hold>`: let go of the hold's objects in batches, clearing the
    S3 hold only where no other hold names the object, then mark the hold released."""

    @workflow.run
    async def run(self, given: LegalHoldInput) -> str:
        pending = await workflow.execute_activity(
            "legal_hold.release_batch",
            given,
            result_type=int,
            start_to_close_timeout=_HOLD_TIMEOUT,
            retry_policy=_HOLD_RETRY,
        )
        while pending > 0:
            pending = await workflow.execute_activity(
                "legal_hold.release_batch",
                given,
                result_type=int,
                start_to_close_timeout=_HOLD_TIMEOUT,
                retry_policy=_HOLD_RETRY,
            )
        return await workflow.execute_activity(
            "legal_hold.finish_release",
            given,
            result_type=str,
            start_to_close_timeout=_TIMEOUT,
            retry_policy=_HOLD_RETRY,
        )


@workflow.defn(name="trust_layer_backfill")
class TrustLayerBackfill:
    """P-03 §4.5 (P-03-T05): one tenant's uploads that have no word layer get one, by the same
    activity as new uploads (idempotent). From v2 (P-03-T15) the uploads without a masked
    rendition get the layer, the scan and the rendition. Batches of `BACKFILL_BATCH` by id
    cursor, so a file that yields no layer is passed, never retried forever, and one whose step
    fails after its retries is counted (`failed`) and passed too, so the backfill never wedges
    on it. Continues as new while a batch is full. Started by an operator command
    (`abacus_tools.trust_layer_backfill`)."""

    @workflow.run
    async def run(self, given: BackfillInput) -> int:
        # v2 (P-03-T15): uploads without a masked rendition get the word layer, the PII scan and
        # the masked rendition, in that order (each idempotent, so a done step costs a read).
        masks = workflow.patched("masks")
        batch = await workflow.execute_activity(
            "trust_layer.pending_masks" if masks else "trust_layer.pending_words",
            given,
            result_type=list[UploadInput],
            start_to_close_timeout=_TIMEOUT,
            retry_policy=_RETRY,
        )
        steps = (
            (("upload.words", int), ("upload.pii_scan", int), ("upload.masked_preview", str))
            if masks
            else (("upload.words", int),)
        )
        failed = 0
        for upload in batch:
            try:
                for name, result in steps:
                    await workflow.execute_activity(
                        name,
                        upload,
                        result_type=result,
                        start_to_close_timeout=_TIMEOUT,
                        retry_policy=_RETRY,
                    )
            except ActivityError:
                failed += 1
                workflow.logger.warning(
                    "trust_layer.upload_failed",
                    extra={"kind": upload.kind, "source_id": upload.source_id},
                )
        versions = [u.source_id for u in batch if u.kind == VERSION]
        inbox = [u.source_id for u in batch if u.kind != VERSION]
        reached = BackfillInput(
            given.tenant_id,
            versions[-1] if versions else given.after_version,
            inbox[-1] if inbox else given.after_inbox,
            given.done + len(batch),
            given.failed + failed,
        )
        if len(batch) >= BACKFILL_BATCH:
            workflow.continue_as_new(reached)
        return reached.done


# --- Engagement export (A-01-T19; A-01 §4.5; SPEC-344). v1, recorded in its histories. ----------

# Bookkeeping must land whatever the outage: the export never stays `queued` or `packaging`.
_EXPORT_STAMP_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=5),
    maximum_attempts=0,
)
# The grant is retried while it is not yet due (the business clock may run behind the timer).
_EXPORT_GRANT_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=30),
    maximum_attempts=20,
)
# A decided failure (a swapped object, a missing section) is never retried.
_EXPORT_BUILD_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=5),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=2),
    maximum_attempts=4,
    non_retryable_error_types=[INTEGRITY_MISMATCH, SECTION_MISSING],
)
_EXPORT_BUILD_TIMEOUT = timedelta(minutes=60)
_EXPORT_HEARTBEAT = timedelta(minutes=2)


def _failure_code(error: ActivityError) -> str:
    cause = error.cause
    if isinstance(cause, ApplicationError) and cause.type in (INTEGRITY_MISMATCH, SECTION_MISSING):
        return cause.type
    return BUILD_ERROR


@workflow.defn(name="engagement_export")
class EngagementExportWorkflow:
    """`engagement_export:<tenant>:<export_id>` (reuse rejected): sleep out the Undo window on a
    durable timer, consume the grant (an Undo voided it: the run ends `undone`), snapshot the
    selection at one audit sequence, build and store the package, then mark it ready; any build
    failure marks it failed with its code. Nothing is published before `mark_ready`."""

    @workflow.run
    async def run(self, given: EngagementExportInput) -> str:
        if given.wait_seconds > 0:
            await workflow.sleep(timedelta(seconds=given.wait_seconds))
        try:
            started = await workflow.execute_activity(
                "engagement_export.consume_grant",
                given,
                result_type=str,
                start_to_close_timeout=_TIMEOUT,
                retry_policy=_EXPORT_GRANT_RETRY,
            )
        except ActivityError:  # retries spent: the export never stays `queued`
            return await self._failed(given, BUILD_ERROR)
        if started != "packaging":
            return started
        try:
            await workflow.execute_activity(
                "engagement_export.snapshot",
                given,
                result_type=int,
                start_to_close_timeout=_TIMEOUT,
                retry_policy=_RETRY,
            )
            facts = await workflow.execute_activity(
                "engagement_export.package",
                given,
                result_type=ExportPackageFacts,
                start_to_close_timeout=_EXPORT_BUILD_TIMEOUT,
                heartbeat_timeout=_EXPORT_HEARTBEAT,
                retry_policy=_EXPORT_BUILD_RETRY,
            )
        except ActivityError as error:
            return await self._failed(given, _failure_code(error))
        return await workflow.execute_activity(
            "engagement_export.mark_ready",
            facts,
            result_type=str,
            start_to_close_timeout=_TIMEOUT,
            retry_policy=_EXPORT_STAMP_RETRY,
        )

    async def _failed(self, given: EngagementExportInput, code: str) -> str:
        return await workflow.execute_activity(
            "engagement_export.mark_failed",
            ExportFailure(given.tenant_id, given.export_id, code),
            result_type=str,
            start_to_close_timeout=_TIMEOUT,
            retry_policy=_EXPORT_STAMP_RETRY,
        )
