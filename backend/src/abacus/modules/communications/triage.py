"""Intake attachments through the upload steps (N-01-T12; N-01 §4.4; DEC-1058).

- `resolve_attachment`: the storage facts evidence's upload steps read for an attachment
  (registered with `evidence.api.register_intake_source`); a withdrawn attachment resolves to
  nothing, so nothing more is derived from it.
- `on_attachment_received`: starts `AttachmentTriage` once per attachment, with
  `inbox.firm_intake` on.
- `attachment_triaged`: after the steps, a New attachment whose thread is matched to a client
  becomes Waiting (`inbox_attachment.waiting`); an unmatched one stays New for the intake scope.
"""

from __future__ import annotations

from typing import Final
from uuid import UUID

from sqlalchemy import text
from temporalio import activity
from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy

from abacus.kernel._flags import INBOX_FIRM_INTAKE
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.dispatch import WorkClass, dispatch, register_work_classes
from abacus.kernel.flags import flag_enabled
from abacus.kernel.uow import OutboxEvent, Ref, Target, uow
from abacus.modules.communications.triage_workflow import (
    AttachmentTriageWorkflow,
    TriageInput,
    attachment_triage_id,
)
from abacus.modules.evidence.api import IntakeSource, register_intake_source

# Interactive: Grace is usually waiting on the row. The plan's background lane above 20 pages
# needs a page count before extraction, which ingest does not keep yet (DEC-1058).
WORKFLOWS: dict[type, WorkClass] = {AttachmentTriageWorkflow: "interactive"}
register_work_classes(WORKFLOWS)
_ACTOR: Final = "communications.attachment_triage"


def _system(tenant_id: UUID) -> TenantContext:
    return TenantContext(tenant_id, "system", _ACTOR)


async def resolve_attachment(tenant: TenantContext, attachment_id: UUID) -> IntakeSource | None:
    async with tenant_session(tenant) as session:
        row = (
            await session.execute(
                text(
                    "SELECT id, storage_key, storage_version_id, fingerprint, size_bytes, "
                    "media_type, key_mode FROM inbox_attachments "
                    "WHERE id = :id AND status <> 'withdrawn'"
                ),
                {"id": attachment_id},
            )
        ).one_or_none()
    if row is None:
        return None
    return IntakeSource(
        id=row.id,
        tenant_id=tenant.tenant_id,
        storage_key=row.storage_key,
        storage_version_id=row.storage_version_id or "",
        fingerprint=row.fingerprint,
        size_bytes=int(row.size_bytes),
        media_type=row.media_type,
        detached_key=row.id if row.key_mode == "detached" else None,
    )


register_intake_source(resolve_attachment)


async def on_attachment_received(event: OutboxEvent) -> None:
    tenant_id = event.tenant_id
    if not await flag_enabled(_system(tenant_id), INBOX_FIRM_INTAKE):
        return
    attachment = str(event.payload["attachment_id"])
    await dispatch(
        AttachmentTriageWorkflow,
        TriageInput(str(tenant_id), attachment),
        id=attachment_triage_id(str(tenant_id), attachment),
        id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
    )


@activity.defn(name="communications.attachment_triaged")
async def attachment_triaged(given: TriageInput) -> str:
    tenant = _system(UUID(given.tenant_id))
    attachment_id = UUID(given.attachment_id)
    async with uow(tenant) as tx:
        moved = (
            await tx.session.execute(
                text(
                    "UPDATE inbox_attachments SET status = 'waiting' "
                    "WHERE id = :id AND status = 'new' AND client_id IS NOT NULL "
                    "RETURNING status"
                ),
                {"id": attachment_id},
            )
        ).scalar_one_or_none()
        status = (
            moved
            or (
                await tx.session.execute(
                    text("SELECT status FROM inbox_attachments WHERE id = :id"),
                    {"id": attachment_id},
                )
            ).scalar_one_or_none()
            or "gone"
        )
        tx.record(
            "inbox_attachment.waiting" if moved else "inbox_attachment.triaged",
            target=Target("inbox_attachment", attachment_id),
            after=Ref(moved=1 if moved else 0),
        )
    return str(status)


ACTIVITIES: Final = (attachment_triaged,)
