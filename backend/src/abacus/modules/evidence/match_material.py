"""What the matcher agent may see of an inbox file (SPEC-033; TASK-065).

The extraction's text (an excerpt for the model, the full pages and sheets for citation checks)
and the candidate requests: the uploader's assignable open requests, scored by code's content
rules (TASK-064), best first, at most 60 (SPEC-033 Q4). Code computes; the matcher judges
(ADR-050). For an agent run authorised on the file's engagement.

Every file reaches the matcher only as its masked projection (P-03-T15; SPEC-322 AC-25, AC-40;
DEC-322, DEC-369): each PII-scanned page's words with every detected region replaced by its token,
and each sheet's cells masked by code; a page no scan covers is left out, and a document with page
text has no material at all until its scan has run (fail closed). The scan then re-announces the
file (a firm file from `pii`, a portal drop from its sort).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final
from uuid import UUID

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.evidence.inbox import inbox_context
from abacus.modules.evidence.matching import Reason, facts_of, score_all, should_match
from abacus.modules.evidence.models import InboxFile, UploadExtraction
from abacus.modules.evidence.processing import excerpt_of, masked_document_text, material_ready
from abacus.modules.evidence.repository import get_inbox_file, newest_extraction
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


async def _candidates(
    tenant: TenantContext, file: InboxFile, row: UploadExtraction
) -> tuple[tuple[Candidate, ...], bool]:
    """The uploader's assignable open requests, scored, and whether the matcher is worth running
    (SPEC-033 Q3). None to choose from when the uploader is no longer a member."""
    uploader = await member_context(tenant.tenant_id, file.uploaded_by)
    if uploader is None:
        return (), False
    items = await request_items_for(uploader, file.engagement_id)
    context = await inbox_context(uploader, file.engagement_id, items)
    scored = score_all(file.file_name, items, facts_of(row), context)[:MAX_CANDIDATES]
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
    return candidates, should_match(scored)


async def _file_and_extraction(
    tenant: TenantContext, inbox_file_id: UUID
) -> tuple[InboxFile, UploadExtraction] | None:
    async with tenant_session(tenant) as session:
        file = await get_inbox_file(session, inbox_file_id)
        row = (
            None if file is None else await newest_extraction(session, inbox_file_id=inbox_file_id)
        )
    return None if file is None or row is None else (file, row)


async def worth_matching(tenant: TenantContext, inbox_file_id: UUID) -> bool:
    """SPEC-033 Q3 (TASK-066 D3): an extracted file with candidates where code wasn't decisive,
    without reading the document itself (the engagement agent's P-7 asks before starting)."""
    found = await _file_and_extraction(tenant, inbox_file_id)
    if found is None or found[1].status != "extracted":
        return False
    async with tenant_session(tenant) as session:
        ready = await material_ready(session, found[1])
    if not ready:
        return False  # not scanned for PII yet: nothing an agent may read (DEC-322, DEC-369)
    candidates, worth = await _candidates(tenant, *found)
    return bool(candidates) and worth


async def match_material(tenant: TenantContext, inbox_file_id: UUID) -> MatchMaterial | None:
    """None without the file or its extraction, or before its PII scan when it has page text:
    only the masked projection is ever material (P-03-T15)."""
    found = await _file_and_extraction(tenant, inbox_file_id)
    if found is None:
        return None
    file, row = found
    text = await masked_document_text(tenant, row)
    if text is None:
        return None  # not scanned yet: nothing for an agent (fail closed)
    pages, sheets = text
    candidates, worth = await _candidates(tenant, file, row)
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
