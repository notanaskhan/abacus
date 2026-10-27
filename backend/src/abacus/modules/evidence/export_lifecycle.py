"""Engagement exports never outlive their content (A-01-T22; SPEC-344 AC-15; A-01 §3.6 Story 6.4,
§4.5; P-14, P-31; DEC-537, DEC-538). PROTECTED (evidence, red).

- **Expiry** (`ExportExpirySweep`, the daily Schedule `export_expiry:platform`): firm by firm,
  under that firm's own system context and business clock, every `ready` export whose
  `expires_at` has passed becomes `expired` (`void_reason = 'expired'`), audited
  `engagement_export.expired`, with the outbox event `engagement_export.expired`. The download
  already answers 410 from `expires_at` itself, so a late or paused sweep never serves a stale
  bundle; the sweep is what cleans up.
- **Void on withdrawal** (the `evidence_version.withdrawn` subscriber, at least once): every
  export holding the withdrawn version (`engagement_export_contents`) that is `ready` becomes
  `expired` with `withdrawn_content`, audited `engagement_export.voided`, outbox
  `engagement_export.voided`. The rows are locked first, `packaging` ones included, so a build
  finishing at the same moment is decided one way or the other: `mark_ready` locks the same row
  and checks the withdrawals after its lock (`settle_ready`), so whichever commits second sees
  the other. The download refuses a bundle holding a withdrawn version even before either runs.
- **Segments** (the `engagement_export.expired` / `.voided` subscriber): once the row says
  `expired`, the export's own segments, and only those (`exports/<tenant>/<export_id>/segment-N`,
  `export_storage.delete_segments`), are deleted; idempotent, retried by the relay. The bucket's
  lifecycle rule (Q-01) is the backstop.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Final
from uuid import UUID

from sqlalchemy import select, update
from temporalio import activity

from abacus.kernel import clock
from abacus.kernel.clock import system_now
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.dispatch import PlatformSchedule, WorkClass, register_work_classes
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import Handler, OutboxEvent, Ref, Scope, Target, UnitOfWork, uow
from abacus.modules.evidence.events import FulfilmentVoided
from abacus.modules.evidence.export_events import (
    EngagementExportExpired,
    EngagementExportReady,
    EngagementExportVoided,
)
from abacus.modules.evidence.export_models import EngagementExport, EngagementExportContent
from abacus.modules.evidence.export_storage import delete_segments
from abacus.modules.evidence.withdrawals import withdrawn_among
from abacus.modules.evidence.workflows import EXPORT_EXPIRY_ID, ExportExpirySweepWorkflow
from abacus.modules.identity.api import firm_tenant_ids

SUBJECT: Final = "engagement_export"
SWEEP_BATCH: Final = 200
WITHDRAWN: Final = "withdrawn_content"
EXPIRED: Final = "expired"
_log = get_logger(__name__)


class _Nothing(Exception):
    """Nothing to write: leave the unit of work without a commit (and without an audit row)."""


def _scope(row: EngagementExport) -> Scope:
    return Scope(engagement_id=row.engagement_id, work_item_id=row.work_item_id)


def _fields(row: EngagementExport) -> dict[str, UUID]:
    return {
        "export_id": row.id,
        "engagement_id": row.engagement_id,
        "work_item_id": row.work_item_id,
        "requested_by": row.requested_by,
    }


async def _close(tx: UnitOfWork, row: EngagementExport, reason: str) -> None:
    """`ready` -> `expired` with its reason, audited, with its outbox event (the guard checks the
    move and that a reason is named)."""
    await tx.session.execute(
        update(EngagementExport)
        .where(EngagementExport.id == row.id, EngagementExport.status == "ready")
        .values(status="expired", void_reason=reason)
    )
    if reason == WITHDRAWN:
        tx.record(
            "engagement_export.voided",
            target=Target(SUBJECT, row.id),
            scope=_scope(row),
        )
        tx.emit(EngagementExportVoided(**_fields(row)))
    else:
        tx.record(
            "engagement_export.expired",
            target=Target(SUBJECT, row.id),
            scope=_scope(row),
        )
        tx.emit(EngagementExportExpired(**_fields(row)))


async def _contents(tenant: TenantContext, export_id: UUID) -> list[UUID]:
    async with tenant_session(tenant) as session:
        return list(
            (
                await session.execute(
                    select(EngagementExportContent.evidence_version_id).where(
                        EngagementExportContent.export_id == export_id
                    )
                )
            )
            .scalars()
            .all()
        )


# --- mark ready (the workflow's last step) -------------------------------------------------------


@dataclass(frozen=True)
class ReadyStamps:
    bundle_sha256: str
    manifest_sha256: str
    bytes: int
    file_count: int
    request_count: int
    segment_count: int
    object_prefix: str
    ready_at: datetime
    expires_at: datetime


async def settle_ready(
    tx: UnitOfWork, tenant: TenantContext, row: EngagementExport, stamps: ReadyStamps
) -> str:
    """Inside `mark_ready`'s unit of work, with the export row locked: write the stamps and
    `ready`; if a version it holds was withdrawn meanwhile, void it at once (no `ready` event, so
    no notification), else emit `engagement_export.ready`."""
    await tx.session.execute(
        update(EngagementExport)
        .where(EngagementExport.id == row.id, EngagementExport.status == "packaging")
        .values(status="ready", **asdict(stamps))
    )
    tx.record(
        "engagement_export.packaged",
        target=Target(SUBJECT, row.id),
        after=Ref(
            files=stamps.file_count,
            requests=stamps.request_count,
            bytes=stamps.bytes,
            bundle=stamps.bundle_sha256,
            manifest=stamps.manifest_sha256,
        ),
        scope=_scope(row),
    )
    if await withdrawn_among(tenant, await _contents(tenant, row.id)):
        await _close(tx, row, WITHDRAWN)
        return EXPIRED
    tx.emit(EngagementExportReady(**_fields(row)))
    return "ready"


# --- void on withdrawal --------------------------------------------------------------------------


async def void_holding(tenant_id: UUID, version_id: UUID) -> int:
    """Void every ready export holding `version_id`; how many. Locks `packaging` rows too, so a
    build committing `ready` at this moment is waited for and then voided."""
    system = TenantContext(tenant_id, "system", "engagement_export:void")
    holding = select(EngagementExportContent.export_id).where(
        EngagementExportContent.evidence_version_id == version_id
    )
    try:
        async with uow(system) as tx:
            rows = (
                (
                    await tx.session.execute(
                        select(EngagementExport)
                        .where(
                            EngagementExport.id.in_(holding),
                            EngagementExport.status.in_(("packaging", "ready")),
                        )
                        .order_by(EngagementExport.id)
                        .with_for_update()
                        .execution_options(populate_existing=True)
                    )
                )
                .scalars()
                .all()
            )
            ready = [r for r in rows if r.status == "ready"]
            if not ready:
                raise _Nothing
            for row in ready:
                await _close(tx, row, WITHDRAWN)
    except _Nothing:
        return 0
    return len(ready)


async def on_version_withdrawn(event: OutboxEvent) -> None:
    await void_holding(event.tenant_id, UUID(str(event.payload["evidence_version_id"])))


async def on_fulfilment_voided(event: OutboxEvent) -> None:
    """L4: a voided rule link retires its version (`EvidenceVersionVoid`, R-01 Story 2.2) just
    as a withdrawal does; a ready bundle holding a retired version is voided the same way."""
    tenant = TenantContext(event.tenant_id, "system", "engagement_export:void")
    version = UUID(str(event.payload["evidence_version_id"]))
    if version in await withdrawn_among(tenant, [version]):
        await void_holding(event.tenant_id, version)


# --- expiry --------------------------------------------------------------------------------------


async def expire_due(tenant_id: UUID) -> int:
    """One firm: every ready export past `expires_at` on its business clock becomes `expired`, in
    batches; how many."""
    system = TenantContext(tenant_id, "system", "engagement_export:sweep")
    expired = 0
    while True:
        # L5 (DEC-546): whichever clock is later, so a business clock held behind never keeps
        # a bundle past the real 7 days.
        now: datetime = max(await clock.now(system), system_now())
        try:
            async with uow(system) as tx:
                rows: Sequence[EngagementExport] = (
                    (
                        await tx.session.execute(
                            select(EngagementExport)
                            .where(
                                EngagementExport.status == "ready",
                                EngagementExport.expires_at <= now,
                            )
                            .order_by(EngagementExport.expires_at, EngagementExport.id)
                            .limit(SWEEP_BATCH)
                            .with_for_update(skip_locked=True)
                        )
                    )
                    .scalars()
                    .all()
                )
                if not rows:
                    raise _Nothing
                for row in rows:
                    await _close(tx, row, EXPIRED)
        except _Nothing:
            return expired
        expired += len(rows)
        if len(rows) < SWEEP_BATCH:
            return expired


@activity.defn(name="engagement_export.expire_sweep")
async def expire_sweep_activity() -> int:
    """Every firm; one firm's failure is logged by id and the others still run."""
    total = 0
    for tenant in await firm_tenant_ids():
        activity.heartbeat(str(tenant))  # L6: a long run reports progress per firm
        try:
            total += await expire_due(tenant)
        except Exception as exc:
            _log.error("export_expiry.failed", tenant_id=str(tenant), error=type(exc).__name__)
    return total


# --- segments ------------------------------------------------------------------------------------


async def on_closed(event: OutboxEvent) -> None:
    """`engagement_export.expired` / `.voided`: delete the segments once the row (read under the
    event's tenant, never the payload's word) says `expired`."""
    export_id = UUID(str(event.payload["export_id"]))
    reader = TenantContext(event.tenant_id, "system", "engagement_export:segments")
    async with tenant_session(reader) as session:
        row = await session.get(EngagementExport, export_id)
    if row is None or row.status != "expired":
        return
    deleted = await delete_segments(row.tenant_id, row.id)
    _log.info("export_segments.deleted", export_id=str(row.id), deleted=deleted)


SUBSCRIPTIONS: dict[str, Handler] = {
    EngagementExportExpired.event_type: on_closed,
    EngagementExportVoided.event_type: on_closed,
    FulfilmentVoided.event_type: on_fulfilment_voided,  # L4
}
WORKFLOWS: dict[type, WorkClass] = {ExportExpirySweepWorkflow: "background"}
register_work_classes(WORKFLOWS)
ACTIVITIES: tuple[object, ...] = (expire_sweep_activity,)
SCHEDULES: tuple[PlatformSchedule, ...] = (
    PlatformSchedule(
        id=EXPORT_EXPIRY_ID,
        workflow=ExportExpirySweepWorkflow,
        every=timedelta(days=1),
        note="A-01-T22: mark ready engagement exports past their 7 days expired",
    ),
)


__all__ = [
    "ACTIVITIES",
    "SCHEDULES",
    "SUBSCRIPTIONS",
    "WORKFLOWS",
    "ReadyStamps",
    "expire_due",
    "expire_sweep_activity",
    "on_closed",
    "on_version_withdrawn",
    "settle_ready",
    "void_holding",
]
