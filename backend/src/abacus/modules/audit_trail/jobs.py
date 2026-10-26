"""The audit trail's platform jobs on Temporal Schedules (Q-02-T20, Q-02-T21; Q-01-T26).

Each activity works firm by firm under that firm's own system context (`kernel.uow.chain`), so
row-level security holds; one firm's failure is logged and the others still run. A chain
mismatch is counted (`audit_chain_mismatches`, the SEV1 alarm's metric) and fails the nightly run
with the checkpoint numbers, never the rows. The daily anchor is evidence's job (ADR-008).
"""

from __future__ import annotations

from datetime import timedelta

from temporalio import activity
from temporalio.exceptions import ApplicationError

from abacus.kernel.access import ensure_partitions
from abacus.kernel.clock import system_now
from abacus.kernel.dispatch import PlatformSchedule, WorkClass, register_work_classes
from abacus.kernel.logging import get_logger
from abacus.kernel.uow.chain import seal_checkpoint, verify_chain
from abacus.modules.audit_trail.workflows import (
    CHECKPOINT_ID,
    PARTITIONS_ID,
    VERIFY_ID,
    AuditChainVerifyWorkflow,
    AuditCheckpointWorkflow,
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
    bad: dict[str, list[int]] = {}
    firms = await firm_tenant_ids()
    for tenant in firms:
        found = await verify_chain(tenant)
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
    return len(firms)


WORKFLOWS: dict[type, WorkClass] = {
    AuditPartitionsWorkflow: "background",
    AuditCheckpointWorkflow: "background",
    AuditChainVerifyWorkflow: "batch",
}
register_work_classes(WORKFLOWS)
ACTIVITIES: tuple[object, ...] = (
    ensure_partitions_activity,
    seal_checkpoints_activity,
    verify_chains_activity,
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
)
