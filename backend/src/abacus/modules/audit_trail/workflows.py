"""The audit trail's platform jobs (Q-02-T20, Q-02-T21; ADR-016, ADR-017). Orchestration only:
activities by name, started only by their Schedules (overlap SKIP), so two workers never run one
twice.

- `AuditPartitions` (monthly): this month's and the next two months' `access_events` partitions.
- `AuditCheckpoint` (every 5 minutes): seals each firm's settled events into its next checkpoint.
- `AuditChainVerify` (nightly): recomputes each firm's chain; a mismatch fails the run (SEV1).
- `AuditLabelIndexer` (every 60 seconds; G-02-T10, G-02 §4.5, DEC-453): tails each firm's
  `audit_events` by `seq` into `audit_event_labels`; idempotent on `(tenant_id, seq)`. A search
  still catches its firm up by one batch first, as the fallback while a run is late or paused.

The daily anchor to the records bucket is evidence's (`evidence/anchor_job.py`): evidence owns
the records bucket and the audit trail may not depend on it (ADR-008).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Final

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError

PARTITIONS_ID: Final = "audit_partitions:platform"
CHECKPOINT_ID: Final = "audit_checkpoint:platform"
VERIFY_ID: Final = "audit_chain_verify:platform"
LABELS_ID: Final = "audit_labels:platform"
_LABELS_TIMEOUT: Final = timedelta(minutes=5)
_TIMEOUT: Final = timedelta(minutes=10)
_VERIFY_TIMEOUT: Final = timedelta(minutes=50)
_RETRY: Final = RetryPolicy(maximum_attempts=3)  # a failed run is retried by the next one
# A mismatch is a finding, not a fault: retrying would only report it again.
_VERIFY_RETRY: Final = RetryPolicy(
    maximum_attempts=3, non_retryable_error_types=["AuditChainMismatch"]
)


@workflow.defn(name="AuditPartitions")
class AuditPartitionsWorkflow:
    @workflow.run
    async def run(self) -> int:
        return await workflow.execute_activity(
            "audit_trail.ensure_partitions",
            result_type=int,
            start_to_close_timeout=_TIMEOUT,
            retry_policy=_RETRY,
        )


@workflow.defn(name="AuditCheckpoint")
class AuditCheckpointWorkflow:
    @workflow.run
    async def run(self) -> int:
        return await workflow.execute_activity(
            "audit_trail.seal_checkpoints",
            result_type=int,
            start_to_close_timeout=_TIMEOUT,
            retry_policy=_RETRY,
        )


@workflow.defn(name="AuditChainVerify")
class AuditChainVerifyWorkflow:
    @workflow.run
    async def run(self) -> int:
        return await workflow.execute_activity(
            "audit_trail.verify_chains",
            result_type=int,
            start_to_close_timeout=_VERIFY_TIMEOUT,
            retry_policy=_VERIFY_RETRY,
        )


@workflow.defn(name="AuditLabelIndexer")
class AuditLabelIndexerWorkflow:
    """v1 (G-02-T10 follow-up; ADR-090): one activity per run. A change to what it schedules goes
    behind `workflow.patched`, so `audit-labels-v1-indexed.json` keeps replaying."""

    @workflow.run
    async def run(self) -> int:
        return await workflow.execute_activity(
            "audit_trail.index_labels",
            result_type=int,
            start_to_close_timeout=_LABELS_TIMEOUT,
            retry_policy=_RETRY,
        )


# --- AuditExportWorkflow (G-02-T17; G-02 §4.5). v1, recorded in its histories. ------------------

EXPORT_BUILD_ERROR: Final = "build_error"
# Decided failures, never retried: the requester left the firm, or nothing signs the manifest.
EXPORT_DECIDED: Final = ("requester_not_member", "signing_unavailable", "exports_unavailable")
_EXPORT_TIMEOUT: Final = timedelta(minutes=2)
_EXPORT_BUILD_TIMEOUT: Final = timedelta(minutes=30)
_EXPORT_HEARTBEAT: Final = timedelta(minutes=2)
_EXPORT_BUILD_RETRY: Final = RetryPolicy(
    maximum_attempts=3, non_retryable_error_types=list(EXPORT_DECIDED)
)
_EXPORT_STAMP_RETRY: Final = RetryPolicy(maximum_attempts=10)


def audit_export_workflow_id(tenant_id: str, export_id: str) -> str:
    return f"audit_export:{tenant_id}:{export_id}"


@dataclass(frozen=True)
class AuditExportInput:
    tenant_id: str
    export_id: str


@dataclass(frozen=True)
class AuditExportFacts:
    """What the build stored: digests, counts and the seq range (no content)."""

    tenant_id: str
    export_id: str
    row_count: int
    seq_from: int | None
    seq_to: int | None
    csv_sha256: str
    manifest_sha256: str
    bundle_bytes: int
    segment_count: int
    signature_key_ref: str


@dataclass(frozen=True)
class AuditExportFailure:
    tenant_id: str
    export_id: str
    code: str


def _export_failure(error: ActivityError) -> str:
    cause = error.cause
    if isinstance(cause, ApplicationError) and cause.type in EXPORT_DECIDED:
        return cause.type
    return EXPORT_BUILD_ERROR


@workflow.defn(name="audit_export")
class AuditExportWorkflow:
    """`audit_export:<tenant>:<export_id>` (reuse rejected): build and store the bundle (CSV,
    `manifest.json`, `manifest.sig`, sealed in the exports bucket), then mark it ready; a failed
    build marks it failed with its code. Nothing is downloadable before `mark_ready`."""

    @workflow.run
    async def run(self, given: AuditExportInput) -> str:
        try:
            facts = await workflow.execute_activity(
                "audit_export.build",
                given,
                result_type=AuditExportFacts,
                start_to_close_timeout=_EXPORT_BUILD_TIMEOUT,
                heartbeat_timeout=_EXPORT_HEARTBEAT,
                retry_policy=_EXPORT_BUILD_RETRY,
            )
        except ActivityError as error:
            return await workflow.execute_activity(
                "audit_export.mark_failed",
                AuditExportFailure(given.tenant_id, given.export_id, _export_failure(error)),
                result_type=str,
                start_to_close_timeout=_EXPORT_TIMEOUT,
                retry_policy=_EXPORT_STAMP_RETRY,
            )
        return await workflow.execute_activity(
            "audit_export.mark_ready",
            facts,
            result_type=str,
            start_to_close_timeout=_EXPORT_TIMEOUT,
            retry_policy=_EXPORT_STAMP_RETRY,
        )
