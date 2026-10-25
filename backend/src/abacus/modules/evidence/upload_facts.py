"""What evidence tells requests about a request's latest upload (A-01-T10; C5 v1.1; DEC-313).

Requests holds which version fulfils which request but never imports evidence, so it asks this
provider (`requests.api.register_upload_facts`) for the facts only evidence holds:

- **path label**: the evidence item's stored title (the uploaded file's name, client content and
  untrusted: rendered as text, never as markup);
- **uploaded on**: the version's creation date;
- **uploader kind**: the channel (`client` for a client upload, `firm` for one the firm added for
  the client, `connection` for a retrieved or imported version);
- **match confidence**: the matcher's shown pick (0-100) for the request, when the version
  arrived through the inbox and the matcher proposed that request for its file. A file assigned
  by hand to a request the matcher did not pick has none: the row never shows a number the
  matcher did not give.

Only versions the caller's rows already reached are asked about; nothing is listed here.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Final, Literal
from uuid import UUID

from sqlalchemy import select

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.evidence import inbox
from abacus.modules.evidence.models import EvidenceItem, EvidenceVersion, InboxFile
from abacus.modules.evidence.repository import not_withdrawn
from abacus.modules.evidence.uploads import SOURCE
from abacus.modules.requests.api import UploadFacts

_CONNECTED: Final = frozenset({"retrieved", "imported"})
UploaderKind = Literal["client", "third_party", "firm", "connection"]


def uploader_kind(source: str, method: str) -> UploaderKind:
    """The channel a version arrived through."""
    if method in _CONNECTED:
        return "connection"
    if source == SOURCE:
        return "client"
    return "firm"  # ON_BEHALF_SOURCE, or a file the firm added itself


async def upload_facts(
    tenant: TenantContext, pairs: Sequence[tuple[UUID, UUID]]
) -> Mapping[UUID, UploadFacts]:
    """Facts per version for (request item, version) pairs the caller already read."""
    versions = sorted({v for _, v in pairs})
    if not versions:
        return {}
    async with tenant_session(tenant) as session:
        rows = (
            await session.execute(
                select(
                    EvidenceVersion.id,
                    EvidenceVersion.created_at,
                    EvidenceVersion.source,
                    EvidenceVersion.method,
                    EvidenceItem.title,
                )
                .join(EvidenceItem, EvidenceItem.id == EvidenceVersion.evidence_item_id)
                # DEC-298: a withdrawn version is as if it never arrived.
                .where(EvidenceVersion.id.in_(versions), not_withdrawn())
            )
        ).all()
        files = (
            await session.execute(
                select(InboxFile.id, InboxFile.assigned_version_id, InboxFile.assigned_item_id)
                .join(EvidenceVersion, EvidenceVersion.id == InboxFile.assigned_version_id)
                .where(InboxFile.assigned_version_id.in_(versions), not_withdrawn())
            )
        ).all()
    picks = await inbox.match_picks(tenant, [f[0] for f in files]) if files else {}
    wanted = {v: i for i, v in pairs}
    confidence: dict[UUID, int] = {}
    for file_id, version_id, item_id in files:
        if version_id is None or wanted.get(version_id) != item_id:
            continue
        for picked, score in picks.get(file_id, []):
            if picked == item_id:
                confidence[version_id] = max(0, min(100, int(score)))
                break
    return {
        vid: UploadFacts(
            path_label=title,
            uploaded_on=created.date(),
            uploader_kind=uploader_kind(source, method),
            match_confidence=confidence.get(vid),
        )
        for vid, created, source, method, title in rows
    }
