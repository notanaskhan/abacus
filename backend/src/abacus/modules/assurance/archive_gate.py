"""Interim G9: the audit file archived in the firm's own tool, recorded against a final binder
export (A-01-T23; A-01 §3.5 Story 5.3; OQ-3; DEC-83, P-43, DEC-591). PROTECTED (red path).

While the firm's `assurance_release_mode` is `external`, a manager or the engagement partner
records that the file now lives in the firm's tool, naming the ready final binder export that
left Accrued and the tool's reference ("CaseWare BH-2025-031"):

- **Who.** `assurance.record_archive`: the engagement partner or a manager, with independence
  and a fresh second factor (403 `mfa_required` when stale, DEC-547), a live person's own act
  (INV-1; `assurance.archive_recorded` is on the human-only register).
- **Against what.** The audit is Released (409 `record_out_of_phase`), and the export is this
  work item's ready `final_binder` export, read FOR SHARE in this unit and current: evidence's
  `final_export_for_archive` refuses one that is not (409 `final_export_required`) or whose
  selection changed after its snapshot (409 `export_stale`, the newer event named). The table's
  insert trigger re-reads the export under the same lock (data layer).
- **What.** The insert-only row keeps the export id and its manifest SHA-256 and the reference
  sealed under the tenant key; the derived move to Archived names G9; C1's archived transition
  sets `work_items.archived_at` and archives the engagement once all its work items are, which
  makes it read-only through `authorise` (every write 403). `archive_locked_at` stays NULL: no
  seal, no database immutability (A-07, P-43).

The G9 provider registered for every firm is `g9` below: SPEC-314's in-app lock or this record.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Final
from uuid import UUID

from abacus.kernel import clock
from abacus.kernel.crypto import seal
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.uow import Ref, Scope, Target, uow
from abacus.modules.assurance import completion
from abacus.modules.assurance.external_models import (
    ExternalArchive,
    external_archive_of,
    ref_context,
)
from abacus.modules.assurance.phase import advance_by_gate
from abacus.modules.assurance.record_auth import authorise_record, fresh_mfa_at
from abacus.modules.assurance.release import RecordOutOfPhase, require_external
from abacus.modules.engagements.api import (
    GateFact,
    archive_work_item,
    assurance_item,
    lock_assurance_item,
    lock_ref,
)
from abacus.modules.evidence.api import final_export_for_archive
from abacus.modules.identity.api import AuthContext

ACTION: Final = "assurance.record_archive"
FIRM_TOOL_REF_MAX: Final = 120


@dataclass(frozen=True)
class ArchiveRecord:
    work_item_id: UUID
    export_id: UUID
    manifest_sha256: str
    phase: str
    recorded_at: datetime


async def record_archive(
    ctx: AuthContext, work_item_id: UUID, export_id: UUID, reference: str
) -> ArchiveRecord:
    """Story 5.3: the external archive, against a ready, current final binder export."""
    text = reference.strip()
    if not text or len(text) > FIRM_TOOL_REF_MAX or "\n" in text:
        raise ValueError("firm_tool_ref")  # the contract model bounds it first (422)
    found = await assurance_item(ctx.tenant, work_item_id)
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, found.engagement_id)
        await authorise_record(ctx, ACTION, ref.resource())
        await require_external(ctx.tenant)
        item = await lock_assurance_item(tx, work_item_id)
        if item.phase != "released":
            raise RecordOutOfPhase(facts={"phase": item.phase})
        final = await final_export_for_archive(tx, ctx.tenant, work_item_id, export_id)
        mfa_at = fresh_mfa_at(ctx)
        sealed = await seal(ctx.tenant_id, text.encode(), ref_context(work_item_id))
        row = ExternalArchive(
            work_item_id=item.work_item_id,
            tenant_id=ctx.tenant_id,
            engagement_id=item.engagement_id,
            export_id=final.export_id,
            manifest_sha256=final.manifest_sha256,
            firm_tool_ref_sealed=sealed,
            recorded_by=ctx.user_id,
            actor_kind="human",
            mfa_at=mfa_at,
        )
        tx.session.add(row)
        await advance_by_gate(tx, ctx.tenant, item.engagement_id, "archived", "G9", ctx.user_id)
        engagement_archived = await archive_work_item(
            tx, item.work_item_id, await clock.now(ctx.tenant)
        )
        tx.record(
            "assurance.archive_recorded",
            target=Target("engagement", item.engagement_id),
            after=Ref(
                work_item=item.work_item_id,
                export=final.export_id,
                manifest_sha256=final.manifest_sha256,
                as_of_seq=final.as_of_seq,
                engagement_archived=int(engagement_archived),
                mfa_at=int(mfa_at.timestamp()),
            ),
            scope=Scope(engagement_id=item.engagement_id, work_item_id=item.work_item_id),
        )
        await tx.session.refresh(row)
        return ArchiveRecord(
            item.work_item_id, final.export_id, final.manifest_sha256, "archived", row.recorded_at
        )


async def g9(tenant: TenantContext, engagement_id: UUID) -> GateFact:
    """G9 for every firm: SPEC-314's archive lock, or the external archive record."""
    in_app = await completion.g9(tenant, engagement_id)
    if in_app.met:
        return in_app
    async with tenant_session(tenant) as session:
        recorded = await external_archive_of(session, engagement_id)
    if recorded is not None:
        return GateFact(met=True, blockers=())
    return in_app
