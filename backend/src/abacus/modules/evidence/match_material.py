"""What the matcher agent may see of an inbox file (SPEC-033; TASK-065).

The extraction's text (an excerpt for the model, the full pages and sheets for citation checks)
and the candidate requests: the uploader's assignable open requests, scored by code's content
rules (TASK-064), best first, at most 60 (SPEC-033 Q4). Code computes; the matcher judges
(ADR-050). For an agent run authorised on the file's engagement.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final
from uuid import UUID

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.evidence.extraction import EXTRACTOR_VERSION
from abacus.modules.evidence.inbox import inbox_context
from abacus.modules.evidence.matching import Reason, facts_of, score_all, should_match
from abacus.modules.evidence.processing import document_text, excerpt_of
from abacus.modules.evidence.repository import extraction_for, get_inbox_file
from abacus.modules.identity.api import member_context
from abacus.modules.requests.api import request_items_for

MAX_CANDIDATES: Final = 60


@dataclass(frozen=True)
class Candidate:
    request_item_id: UUID
    description: str
    audit_area: str
    document_kind: str | None
    needed_accounts: tuple[str, ...]
    score: int
    reasons: tuple[Reason, ...]


@dataclass(frozen=True)
class MatchMaterial:
    engagement_id: UUID
    inbox_file_id: UUID
    file_name: str
    extraction_status: str
    candidates: tuple[Candidate, ...]
    worth_matching: bool  # SPEC-033 Q3: false when code's top request is decisive
    excerpt_pages: tuple[tuple[int, str], ...]
    excerpt_tables: tuple[tuple[str, tuple[tuple[str, ...], ...]], ...]
    truncated: bool
    pages: dict[int, str]
    sheets: dict[str, tuple[tuple[str, ...], ...]]


async def match_material(tenant: TenantContext, inbox_file_id: UUID) -> MatchMaterial | None:
    """None without the file or its extraction."""
    async with tenant_session(tenant) as session:
        file = await get_inbox_file(session, inbox_file_id)
        row = (
            None
            if file is None
            else await extraction_for(
                session, inbox_file_id=inbox_file_id, extractor_version=EXTRACTOR_VERSION
            )
        )
    if file is None or row is None:
        return None
    uploader = await member_context(tenant.tenant_id, file.uploaded_by)
    candidates: tuple[Candidate, ...] = ()
    worth = True
    if uploader is not None:
        items = await request_items_for(uploader, file.engagement_id)
        context = await inbox_context(uploader, file.engagement_id, items)
        scored = score_all(file.file_name, items, facts_of(row), context)[:MAX_CANDIDATES]
        worth = should_match(scored)
        described = {i.id: i for i in items}
        needed: Mapping[UUID, frozenset[str]] = context.needed if context is not None else {}
        candidates = tuple(
            Candidate(
                s.request_item_id,
                described[s.request_item_id].description,
                described[s.request_item_id].audit_area,
                described[s.request_item_id].document_kind,
                tuple(sorted(needed.get(s.request_item_id, frozenset()))),
                s.score,
                s.reasons,
            )
            for s in scored
        )
    pages, sheets = await document_text(tenant.tenant_id, row)
    excerpt_pages, excerpt_tables, truncated = excerpt_of(pages, sheets)
    return MatchMaterial(
        file.engagement_id,
        inbox_file_id,
        file.file_name,
        row.status,
        candidates,
        worth,
        excerpt_pages,
        excerpt_tables,
        truncated,
        pages,
        sheets,
    )
