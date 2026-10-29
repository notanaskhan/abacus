"""Detached data keys of client-channel uploads (ADR-162 §5; P-06-T18). PROTECTED.

`storage.get` and `storage.put(..., under=...)` find a detached-key version's wrapped key here.
The read runs as the system on the tenant's own rows: the caller has already authorised the
content read it serves (storage never authorises), and a destroyed key answers None, so an
erased object can't be opened by anyone.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, text

from abacus.kernel.crypto import DetachedKey
from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.evidence.intake_sources import IntakeSource
from abacus.modules.evidence.models import EvidenceObjectKey, EvidenceVersion, InboxFile


async def key_for(tenant_id: UUID, version_id: UUID) -> DetachedKey | None:
    """The version's wrapped key, or None when it was destroyed or never stored."""
    reader = TenantContext(tenant_id, "system", "evidence.object_keys")
    async with tenant_session(reader) as session:
        row = (
            await session.execute(
                select(EvidenceObjectKey).where(
                    EvidenceObjectKey.evidence_version_id == version_id
                )
            )
        ).scalar_one_or_none()
        if row is None:
            # N-01-T14: a portal intake attachment's key (DEC-1060); attachment and version ids
            # never collide.
            intake = (
                await session.execute(
                    text(
                        "SELECT key_id, wrapped_key, destroyed_at "
                        "FROM evidence_intake_object_keys WHERE inbox_attachment_id = :id"
                    ),
                    {"id": version_id},
                )
            ).one_or_none()
            if intake is None or intake.wrapped_key is None or intake.destroyed_at is not None:
                return None
            return DetachedKey(intake.key_id, bytes(intake.wrapped_key))
    if row.wrapped_key is None or row.destroyed_at is not None:
        return None
    return DetachedKey(row.key_id, row.wrapped_key)


def under_key(source: EvidenceVersion | InboxFile | IntakeSource) -> UUID | None:
    """ADR-162 §6: a detached-key version's derived records are sealed under its own key, so
    its erase covers them; anything else's are content-addressed. An intake attachment sealed
    under its own key (ADR-137, N-01-T14) keeps its derivations under it too."""
    if isinstance(source, IntakeSource):
        return source.detached_key
    if isinstance(source, EvidenceVersion) and source.storage_mode == "detached_key":
        return source.id
    return None
