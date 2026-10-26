"""The audit trail's platform jobs on Temporal Schedules (Q-02-T20, Q-02-T21; Q-01-T26).

Each activity works firm by firm under that firm's own system context (`kernel.uow.chain`), so
row-level security holds; one firm's failure is logged and the others still run. A chain
mismatch is counted (`audit_chain_mismatches`, the SEV1 alarm's metric) and fails the nightly run
with the checkpoint numbers, never the rows. The daily anchor is evidence's job (ADR-008).
"""

from __future__ import annotations

import contextlib
from datetime import timedelta

from temporalio import activity
from temporalio.exceptions import ApplicationError

from abacus.kernel.access import ensure_partitions
from abacus.kernel.clock import system_now
from abacus.kernel.dispatch import PlatformSchedule, WorkClass, register_work_classes
from abacus.kernel.logging import get_logger
from abacus.kernel.uow.chain import seal_checkpoint, verify_chain
from abacus.modules.audit_trail.labels import BATCH, IndexBusy, index_batch
from abacus.modules.audit_trail.workflows import (
    CHECKPOINT_ID,
    LABELS_ID,
    PARTITIONS_ID,
    VERIFY_ID,
    AuditChainVerifyWorkflow,
    AuditCheckpointWorkflow,
    AuditLabelIndexerWorkflow,
    AuditPartitionsWorkflow,
)
from abacus.modules.identity.api import firm_tenant_ids

_log = get_logger(__name__)


@activity.defn(name="audit_trail.ensure_partitions")
async def ensure_partitions_activity() -> int:
    return len(await ensure_partitions(system_now().date()))


@activity.defn(name="audit_trail.seal_checkpoints")
async def seal_checkpoints_activity() -> int:
    sealed = 0
    for tenant in await firm_tenant_ids():
        try:
            if await seal_checkpoint(tenant) is not None:
                sealed += 1
        except Exception as exc:
            _log.error("audit_checkpoint.failed", tenant_id=str(tenant), error=type(exc).__name__)
    return sealed


@activity.defn(name="audit_trail.verify_chains")
async def verify_chains_activity() -> int:
    """Every firm is verified even when one fails to: a mismatch anywhere fails the run as
    `AuditChainMismatch` (non-retryable, the SEV1 metric's finding); otherwise a firm that could
    not be read fails it as `AuditChainVerifyFailed`, retried (security review, 2026-10-26)."""
    bad: dict[str, list[int]] = {}
    unread: list[str] = []
    firms = await firm_tenant_ids()
    for tenant in firms:
        try:
            found = await verify_chain(tenant)
        except Exception as exc:
            unread.append(str(tenant))
            _log.error(
                "audit_chain.verify_failed", tenant_id=str(tenant), error=type(exc).__name__
            )
            continue
        if found:
            bad[str(tenant)] = found
            _log.error("audit_chain.mismatch", tenant_id=str(tenant), checkpoints=found)
    if bad:
        raise ApplicationError(
            f"{len(bad)} firm(s) with checkpoints that no longer verify",
            bad,
            type="AuditChainMismatch",
            non_retryable=True,
        )
    if unread:
        raise ApplicationError(
            f"{len(unread)} firm(s) could not be verified", unread, type="AuditChainVerifyFailed"
        )
    return len(firms)


# One run indexes at most this many batches per firm, so a firm with a long history (a back-fill
# is `labels.backfill`, run by an operator) never holds the 60-second run for the others.
LABEL_BATCHES_PER_RUN = 5


@activity.defn(name="audit_trail.index_labels")
async def index_labels_activity() -> int:
    """G-02-T10 (DEC-453): each firm's new events into its label index, a few batches at most.
    Another indexer holding a firm's lock (a search catching up) skips that firm this run; a
    firm that fails is logged by id and the others still run."""
    written = 0
    for tenant in await firm_tenant_ids():
        try:
            for _ in range(LABEL_BATCHES_PER_RUN):
                count = 0
                with contextlib.suppress(IndexBusy):
                    count, _last = await index_batch(tenant)
                written += count
                if count < BATCH:
                    break
        except Exception as exc:
            _log.error("audit_labels.failed", tenant_id=str(tenant), error=type(exc).__name__)
    return written


WORKFLOWS: dict[type, WorkClass] = {
    AuditPartitionsWorkflow: "background",
    AuditCheckpointWorkflow: "background",
    AuditChainVerifyWorkflow: "batch",
    AuditLabelIndexerWorkflow: "background",  # G-02-T10 (DEC-453)
}
register_work_classes(WORKFLOWS)
ACTIVITIES: tuple[object, ...] = (
    ensure_partitions_activity,
    seal_checkpoints_activity,
    verify_chains_activity,
    index_labels_activity,
)
SCHEDULES: tuple[PlatformSchedule, ...] = (
    PlatformSchedule(
        id=PARTITIONS_ID,
        workflow=AuditPartitionsWorkflow,
        every=timedelta(days=30),
        note="Q-02-T20: access_events partitions for this month and the next two",
    ),
    PlatformSchedule(
        id=CHECKPOINT_ID,
        workflow=AuditCheckpointWorkflow,
        every=timedelta(minutes=5),
        note="Q-02-T21: seal each firm's settled audit events into its next checkpoint",
    ),
    PlatformSchedule(
        id=VERIFY_ID,
        workflow=AuditChainVerifyWorkflow,
        every=timedelta(days=1),
        note="Q-02-T21: recompute every firm's hash chain; a mismatch fails the run (SEV1)",
    ),
    PlatformSchedule(
        id=LABELS_ID,
        workflow=AuditLabelIndexerWorkflow,
        every=timedelta(seconds=60),
        note="G-02-T10: tail each firm's audit events into its label index (DEC-453)",
    ),
)
