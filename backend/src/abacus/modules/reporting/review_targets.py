"""The financial-statement package as a C3 reviewable (A-06-T15; AUD-17, AUD-20; DEC-2215).

Each statement document's current version is one `fs_package` reviewable, its content hash the
version's: a new draft leaves the package's sign-offs stale.
"""

from __future__ import annotations

from typing import Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.review.api import Reviewable, ReviewableFacts

FS_TARGET: Final = "fs_package"
_BY_ENGAGEMENT = text(
    "SELECT d.id, d.engagement_id, v.version_no, v.content_hash, v.initiator_user_id "
    "FROM statement_documents d JOIN statement_versions v ON v.tenant_id = d.tenant_id "
    "AND v.statement_document_id = d.id AND v.version_no = d.current_version_no "
    "WHERE d.engagement_id = :e"
)
_BY_DOCUMENT = text(
    "SELECT d.id, d.engagement_id, v.version_no, v.content_hash, v.initiator_user_id "
    "FROM statement_documents d JOIN statement_versions v ON v.tenant_id = d.tenant_id "
    "AND v.statement_document_id = d.id AND v.version_no = d.current_version_no "
    "WHERE d.id = :d"
)


async def fs_reviewables(tenant: TenantContext, engagement_id: UUID) -> list[Reviewable]:
    async with tenant_session(tenant) as session:
        rows = (await session.execute(_BY_ENGAGEMENT, {"e": engagement_id})).mappings().all()
    return [
        Reviewable(
            FS_TARGET,
            cast(UUID, r["id"]),
            "FS",
            "Financial statements",
            cast(str, r["content_hash"]),
            True,
        )
        for r in rows
    ]


async def fs_facts(tenant: TenantContext, document_id: UUID) -> ReviewableFacts | None:
    async with tenant_session(tenant) as session:
        r = (await session.execute(_BY_DOCUMENT, {"d": document_id})).mappings().one_or_none()
    if r is None:
        return None
    return ReviewableFacts(
        FS_TARGET,
        document_id,
        cast(UUID, r["engagement_id"]),
        cast(str, r["content_hash"]),
        int(cast(int, r["version_no"])),
        frozenset({cast(UUID, r["initiator_user_id"])}),
        label="Financial statements",
    )
