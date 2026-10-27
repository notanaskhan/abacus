"""Sealed review texts (P-04-T21, T23; ADR-160 clauses 6 and 8; ADR-031).

Note bodies, event bodies, decision rationales and analysis requests are Restricted: they are
stored sealed (envelope encryption under the firm's key), each bound to its own row and field, so
a sealed value opens only where it was written. Handing one to a person is an access event
(Q-02 `access_events`), recorded before the text leaves; an error there serves nothing.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from uuid import UUID

from abacus.kernel.access import AccessSubject, record_reads, register_access_kind
from abacus.kernel.crypto import open_sealed, seal
from abacus.kernel.db import TenantContext

ACCESS_KIND = "review_content.read"
register_access_kind(ACCESS_KIND, ["restricted"])


def _binding(kind: str, *parts: object) -> str:
    return hashlib.sha256(":".join([kind, *(str(p) for p in parts)]).encode()).hexdigest()


async def seal_text(tenant: TenantContext, text: str, kind: str, *parts: object) -> bytes:
    return await seal(tenant.tenant_id, text.encode(), _binding(kind, *parts))


async def open_text(tenant: TenantContext, sealed: bytes, kind: str, *parts: object) -> str:
    return (await open_sealed(tenant.tenant_id, sealed, _binding(kind, *parts))).decode()


async def record_text_reads(
    tenant: TenantContext,
    subject_type: str,
    subject_ids: Sequence[UUID],
    *,
    engagement_id: UUID,
    client_id: UUID | None,
    work_item_id: UUID | None = None,
) -> None:
    """Before sealed texts are handed over: one identifier-only row per subject."""
    await record_reads(
        tenant,
        ACCESS_KIND,
        [
            AccessSubject(
                subject_type,
                subject_id,
                client_id=client_id,
                engagement_id=engagement_id,
                work_item_id=work_item_id,
            )
            for subject_id in dict.fromkeys(subject_ids)
        ],
    )
