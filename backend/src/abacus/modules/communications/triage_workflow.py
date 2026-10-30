"""`AttachmentTriage` (N-01-T12; N-01 §4.4 step 5; ADR-090; DEC-1058).

Orchestration only, by name: one run per intake attachment (`attachment_triage:<tenant>:<id>`),
started when the attachment is received. It runs evidence's upload steps for the attachment by
name, kind `intake` (the scan already happened at ingest): extraction, the word layer, the PII
scan and the masked preview; then `communications.attachment_triaged` moves a matched attachment
from New to Waiting. A later change lands behind `workflow.patched(...)`: N-01-T17 classifies
and flags the attachment (`communications.attachment_classified`) before that last step.
A step that fails never undoes the ones before it. Identifiers only in the history.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError

_STEP_TIMEOUT = timedelta(minutes=3)
_STEP_RETRY = RetryPolicy(maximum_attempts=6, maximum_interval=timedelta(minutes=1))
# Extraction, the word layer, PII detection, the masked rendition: each step's failure leaves
# the ones before it (a later backfill retries, as for any upload).
_STEPS: tuple[tuple[str, type], ...] = (
    ("upload.extract", str),
    ("upload.words", int),
    ("upload.pii_scan", int),
    ("upload.masked_preview", str),
)
_CLASSIFY_PATCH = "n01-t17-classify"
_TRIAGED_TIMEOUT = timedelta(seconds=30)
_TRIAGED_RETRY = RetryPolicy(maximum_attempts=0, maximum_interval=timedelta(minutes=1))


@dataclass(frozen=True)
class TriageInput:
    tenant_id: str
    attachment_id: str


def attachment_triage_id(tenant_id: str, attachment_id: str) -> str:
    return f"attachment_triage:{tenant_id}:{attachment_id}"


@workflow.defn(name="AttachmentTriage")
class AttachmentTriageWorkflow:
    @workflow.run
    async def run(self, given: TriageInput) -> str:
        # evidence's upload steps by name, for kind `intake` (UploadInput by value: this module
        # imports no other module). The scan already ran at ingest.
        upload = {"tenant_id": given.tenant_id, "kind": "intake", "source_id": given.attachment_id}
        for step, result_type in _STEPS:
            try:
                await workflow.execute_activity(
                    step,
                    upload,
                    result_type=result_type,
                    start_to_close_timeout=_STEP_TIMEOUT,
                    retry_policy=_STEP_RETRY,
                )
            except ActivityError:
                workflow.logger.warning("attachment_triage.step_failed", extra={"step": step})
        # N-01-T17: rule classification and code flags, once the word layer and the PII scan
        # are in place. A failure leaves the attachment unflagged, never stuck.
        if workflow.patched(_CLASSIFY_PATCH):
            try:
                await workflow.execute_activity(
                    "communications.attachment_classified",
                    given,
                    result_type=int,
                    start_to_close_timeout=_STEP_TIMEOUT,
                    retry_policy=_STEP_RETRY,
                )
            except ActivityError:
                workflow.logger.warning(
                    "attachment_triage.step_failed", extra={"step": "classify"}
                )
        return await workflow.execute_activity(
            "communications.attachment_triaged",
            given,
            result_type=str,
            start_to_close_timeout=_TRIAGED_TIMEOUT,
            retry_policy=_TRIAGED_RETRY,
        )
