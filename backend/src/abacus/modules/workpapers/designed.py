"""A-05-T09: what a work item's designed papers are, for their owners' rail rows and export
sections (SPEC-641). Callers have authorised on the work item's engagement."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.workpapers.repository import next_version_no, papers_of_work_item


@dataclass(frozen=True)
class PaperFact:
    id: UUID
    code: str
    kind: str
    title: str
    version_no: int  # 0 before the first version


async def work_item_papers(tenant: TenantContext, work_item_id: UUID) -> list[PaperFact]:
    async with tenant_session(tenant) as session:
        out: list[PaperFact] = []
        for paper in await papers_of_work_item(session, work_item_id):
            out.append(
                PaperFact(
                    paper.id,
                    paper.code,
                    str(paper.kind),
                    paper.title,
                    await next_version_no(session, paper.id) - 1,
                )
            )
        return out
