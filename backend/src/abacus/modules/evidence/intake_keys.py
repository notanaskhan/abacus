"""Portal intake in detached-key mode (N-01-T14; ADR-162 §5; DEC-1060).

A client's portal upload is a client-channel object: it is screened like any upload, then
stored under a data key of its own (`storage.put_detached`, keyed by the intake attachment), and
the wrapped key is kept in `evidence_intake_object_keys` in the unit of work that inserts the
attachment. Its derived records (AttachmentTriage) are sealed under the same key. Withdrawing it
and letting 30 days pass destroys that one row: the object and everything derived from it can no
longer be read (`storage.get` raises `KeyDestroyed`).
"""

from __future__ import annotations

import asyncio
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.clock import system_now
from abacus.kernel.crypto import DetachedKey
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.uow import Ref, Target, UnitOfWork
from abacus.modules.evidence import storage
from abacus.modules.evidence.signed_copies import ScreenedFile
from abacus.modules.evidence.uploads import checked, clean_name


async def screen_and_stage_detached(
    tenant_id: UUID, attachment_id: UUID, content: bytes, file_name: str
) -> tuple[ScreenedFile, DetachedKey]:
    """Scan and type the file (refused closed), then store it under its own key. The caller
    records the key with `record_intake_key` in the unit of work that inserts the attachment."""
    media_type, digest = await asyncio.to_thread(checked, content, file_name)
    stored, key = await storage.put_detached(tenant_id, attachment_id, content)
    return ScreenedFile(clean_name(file_name), media_type, digest, stored), key


async def record_intake_key(
    tx: UnitOfWork, tenant_id: UUID, attachment_id: UUID, key: DetachedKey
) -> None:
    await tx.session.execute(
        text(
            "INSERT INTO evidence_intake_object_keys (tenant_id, inbox_attachment_id, key_id, "
            "wrapped_key) VALUES (:tenant, :attachment, :key_id, :wrapped)"
        ),
        {
            "tenant": tenant_id,
            "attachment": attachment_id,
            "key_id": key.key_id,
            "wrapped": key.wrapped,
        },
    )


async def destroy_intake_key(tx: UnitOfWork, attachment_id: UUID) -> bool:
    """Crypto-erase a withdrawn attachment: its key goes; True when this call erased it. A
    retained key (a hold) is never destroyed."""
    erased = (
        await tx.session.execute(
            text(
                "UPDATE evidence_intake_object_keys SET wrapped_key = NULL, destroyed_at = :now "
                "WHERE inbox_attachment_id = :id AND destroyed_at IS NULL AND retained_at IS NULL "
                "RETURNING inbox_attachment_id"
            ),
            {"now": system_now(), "id": attachment_id},
        )
    ).scalar_one_or_none()
    if erased is not None:
        tx.record(
            "inbox_attachment.key_destroyed",
            target=Target("inbox_attachment", attachment_id),
            after=Ref(attachment_id=attachment_id),
        )
    return erased is not None


async def live_intake_keys(tenant: TenantContext, attachment_ids: list[UUID]) -> frozenset[UUID]:
    """The attachments among these whose key is neither destroyed nor retained (the purge's
    candidates)."""
    if not attachment_ids:
        return frozenset()
    async with tenant_session(tenant) as session:
        rows = await session.execute(
            text(
                "SELECT inbox_attachment_id FROM evidence_intake_object_keys "
                "WHERE inbox_attachment_id = ANY(:ids) AND destroyed_at IS NULL "
                "AND retained_at IS NULL"
            ),
            {"ids": attachment_ids},
        )
        return frozenset(rows.scalars())
