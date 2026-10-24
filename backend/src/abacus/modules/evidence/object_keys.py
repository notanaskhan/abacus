"""Detached data keys of client-channel uploads (ADR-162 §5; P-06-T18). PROTECTED.

`storage.get` and `storage.put(..., under=...)` find a detached-key version's wrapped key here.
The read runs as the system on the tenant's own rows: the caller has already authorised the
content read it serves (storage never authorises), and a destroyed key answers None, so an
erased object can't be opened by anyone.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from abacus.kernel.crypto import DetachedKey
from abacus.kernel.db import TenantContext, tenant_session
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
    if row is None or row.wrapped_key is None or row.destroyed_at is not None:
        return None
    return DetachedKey(row.key_id, row.wrapped_key)


def under_key(source: EvidenceVersion | InboxFile) -> UUID | None:
    """ADR-162 §6: a detached-key version's derived records are sealed under its own key, so
    its erase covers them; anything else's are content-addressed."""
    if isinstance(source, EvidenceVersion) and source.storage_mode == "detached_key":
        return source.id
    return None
