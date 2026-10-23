"""Evidence content reads leave access events (Q-02-T20; AC-23). Identifiers only: the version or
inbox file, its engagement and client, never a file name, quote or value."""

from __future__ import annotations

from uuid import UUID

from abacus.kernel.access import AccessSubject, record_reads, register_access_kind
from abacus.modules.engagements.api import get_ref
from abacus.modules.identity.api import AuthContext

KIND = "evidence_content.read"
register_access_kind(KIND, ["restricted"])


async def record_content_read(
    ctx: AuthContext, engagement_id: UUID, subject_type: str, subject_id: UUID
) -> None:
    """Before content is handed over: an error here means the content is not served."""
    engagement = await get_ref(ctx, engagement_id)
    await record_reads(
        ctx.tenant,
        KIND,
        [
            AccessSubject(
                subject_type,
                subject_id,
                client_id=engagement.client_id,
                engagement_id=engagement_id,
            )
        ],
    )
