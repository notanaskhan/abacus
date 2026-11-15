"""A version's file facts for an owner's read model (T-07-T12: TXT-01's instrument header):
the item's title as the file name, the version's engagement and how many pages it has. For a
caller that has already authorised under its own context; never the content."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import NotFound
from abacus.modules.evidence.models import EvidenceItem, EvidencePage, EvidenceVersion


@dataclass(frozen=True)
class VersionFileFacts:
    version_id: UUID
    engagement_id: UUID
    client_entity_id: UUID | None
    file_name: str
    page_count: int


async def version_file_facts(tenant: TenantContext, version_id: UUID) -> VersionFileFacts:
    async with tenant_session(tenant) as session:
        row = (
            await session.execute(
                select(
                    EvidenceVersion.id,
                    EvidenceVersion.engagement_id,
                    EvidenceVersion.client_entity_id,
                    EvidenceItem.title,
                )
                .join(EvidenceItem, EvidenceItem.id == EvidenceVersion.evidence_item_id)
                .where(EvidenceVersion.id == version_id)
            )
        ).first()
        if row is None:
            raise NotFound("evidence_version")
        pages = await session.scalar(
            select(func.count()).where(EvidencePage.evidence_version_id == version_id)
        )
    return VersionFileFacts(row[0], row[1], row[2], row[3], int(pages or 0))
