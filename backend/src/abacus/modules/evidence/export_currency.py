"""Whether a final binder export can stand for the archive (A-01-T23; A-01 §3.5 Story 5.3;
DEC-591). PROTECTED.

Assurance's record-mode archive (interim G9) is recorded against a ready `final_binder` export
of the same work item. Inside the caller's unit of work the export row is read **FOR SHARE**, so a
withdrawal voiding it, the expiry sweep or another writer waits until the archive commits or
rolls back, and then checked:

- `final_export_required` (409): not this work item's, not `final_binder`, not `ready`, voided,
  or past `expires_at` on the business clock or the system clock (as the download is);
- `export_stale` (409): the selection changed after the snapshot. The requester's selection now
  (the same scope, as the build planned it) must hold exactly the versions and the request count
  the snapshot holds, and no event that changes something (not a read, a preview or a refusal)
  may have been audited about any of its requests or files after `as_of_seq`; the newest such
  event's sequence is the 409's fact. A requester who may no longer read the evidence makes the
  export unusable as well (`export_stale`, reason `requester_access`).

Identifiers and digests only; nothing is decided here (ADR-005).
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select

from abacus.kernel import clock
from abacus.kernel.clock import system_now
from abacus.kernel.db import TenantContext
from abacus.kernel.errors import DomainConflict
from abacus.kernel.uow import UnitOfWork, audit_newest_change
from abacus.modules.evidence.export_models import EngagementExport, EngagementExportContent
from abacus.modules.evidence.export_package import ExportSectionInvalid, SectionRequest
from abacus.modules.evidence.export_sections import acting_person
from abacus.modules.evidence.export_selection import plan_selection
from abacus.modules.evidence.exports import ExportScope

FINAL_BINDER = "final_binder"


class FinalExportRequired(DomainConflict):
    """The archive needs a ready final binder export of this work item: none was named, or the
    one named is not final, not ready, voided or expired."""

    code = "final_export_required"


class ExportStale(DomainConflict):
    """Evidence or requests changed after the final export's snapshot: export again, then
    record the archive (`facts.event_seq` names the newer event)."""

    code = "export_stale"


@dataclass(frozen=True)
class FinalExport:
    export_id: UUID
    manifest_sha256: str
    as_of_seq: int


async def final_export_for_archive(
    tx: UnitOfWork, tenant: TenantContext, work_item_id: UUID, export_id: UUID
) -> FinalExport:
    """The checked export, locked FOR SHARE in `tx` (the caller has authorised the archive on
    the work item's engagement)."""
    row = await tx.session.scalar(
        select(EngagementExport)
        .where(EngagementExport.id == export_id)
        .with_for_update(read=True)
        .execution_options(populate_existing=True)
    )
    if row is None or row.work_item_id != work_item_id:
        raise FinalExportRequired(facts={"reason": "not_found"})
    business_now = await clock.now(tenant)
    if (
        row.kind != FINAL_BINDER
        or row.status != "ready"
        or row.void_reason is not None
        or row.expires_at is None
        or row.manifest_sha256 is None
        or row.as_of_seq is None
        or max(business_now, system_now()) >= row.expires_at
    ):
        raise FinalExportRequired(facts={"reason": "not_ready", "status": row.status})
    snapshot = frozenset(
        (
            await tx.session.execute(
                select(EngagementExportContent.evidence_version_id).where(
                    EngagementExportContent.export_id == row.id
                )
            )
        )
        .scalars()
        .all()
    )
    now_versions, request_ids = await _selection_now(row)
    if now_versions != snapshot or len(request_ids) != row.request_count:
        raise ExportStale(facts={"reason": "selection_changed"})
    targets = [("request_item", r) for r in request_ids]
    targets += [("evidence_version", v) for v in sorted(snapshot | now_versions)]
    newer = await audit_newest_change(tx.session, targets, row.as_of_seq)
    if newer is not None:
        raise ExportStale(facts={"reason": "newer_event", "event_seq": newer[0]})
    return FinalExport(row.id, row.manifest_sha256, row.as_of_seq)


async def _selection_now(row: EngagementExport) -> tuple[frozenset[UUID], list[UUID]]:
    """The requester's selection for the export's scope, as a build would plan it now."""
    tenant = TenantContext(row.tenant_id, "system", "evidence.export_currency")
    scope = ExportScope.of(row.scope)
    try:
        ctx = await acting_person(tenant, row.requested_by)
        plan = await plan_selection(
            ctx,
            SectionRequest(
                export_id=row.id,
                engagement_id=row.engagement_id,
                work_item_id=row.work_item_id,
                binder_ids=scope.binder_ids,
                as_of_seq=row.as_of_seq or 0,
                include_unaccepted=scope.include_unaccepted,
                requested_by_user_id=row.requested_by,
                membership_id=ctx.membership_id,
            ),
        )
    except ExportSectionInvalid:
        raise ExportStale(facts={"reason": "requester_access"}) from None
    return plan.version_ids, [r.request_item_id for r in plan.requests]


__all__ = ["ExportStale", "FinalExport", "FinalExportRequired", "final_export_for_archive"]
