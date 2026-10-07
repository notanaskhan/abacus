"""Knowledge: a firm's methodology documents, chunked, embedded and recalled (SPEC-009).

Facts live in tables; vectors are only for recall (ADR-053). Knowledge is firm-wide in v1: every
read and write is checked on the firm, and search is exact over the caller's firm only, with the
tenant explicit as well as enforced by row-level security (Q1, AC-9). Document text is the
firm's own or public material (ADR-056) and still hostile when it reaches a prompt (ADR-052).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Final, Literal
from uuid import UUID, uuid4

from abacus.ai_gateway import (
    Attribution,
    BudgetExceeded,
    BudgetExhausted,
    EmbedCall,
    EmbedTooLarge,
    NotAdmitted,
    embed,
)
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import MissingAuditEvent, Ref, Target, uow
from abacus.modules.agents.events import KnowledgeDocumentAdded
from abacus.modules.agents.knowledge_chunks import chunk_document
from abacus.modules.agents.models import KnowledgeDocument
from abacus.modules.agents.repository import (
    active_document_with,
    chunks_without_vectors,
    firm_chunk_count,
    get_document,
    insert_chunks,
    insert_document,
    list_documents,
    lock_document,
    nearest_chunks,
    remaining_chunks,
    set_document_status,
    store_vectors,
)
from abacus.modules.agents.workflow_types import BatchOutcome
from abacus.modules.identity.api import AuthContext, Resource, authorise

SourceKind = Literal["firm_own", "public"]
MediaType = Literal["text/plain", "text/markdown"]
MAX_K: Final = 20
MAX_QUERY_CHARS: Final = 1_000
BATCH: Final = 64
EMBEDDER: Final = "knowledge.embedder"
SEARCHER: Final = "knowledge.search"
# Per embedding call: generous for 64 chunks of 1,200 characters at any listed price.
_BATCH_BUDGET: Final = Decimal("0.50")
_QUERY_BUDGET: Final = Decimal("0.01")
_log = get_logger(__name__)


class KnowledgeInvalid(DomainInvalid):
    code = "knowledge_invalid"


class KnowledgeTooLarge(KnowledgeInvalid):
    """Over the document's size or chunk limit, or the firm's chunk limit (§7)."""

    code = "knowledge_too_large"


class KnowledgeEmpty(KnowledgeInvalid):
    code = "knowledge_empty"


class KnowledgeQueryInvalid(KnowledgeInvalid):
    """An empty query, one over 1,000 characters, or k outside 1 to 20."""

    code = "knowledge_query_invalid"


class KnowledgeDuplicate(DomainConflict):
    """The same text is already in the firm's knowledge (not withdrawn)."""

    code = "knowledge_duplicate"


class KnowledgeWithdrawn(DomainConflict):
    code = "knowledge_withdrawn"


@dataclass(frozen=True)
class NewDocument:
    title: str
    source_kind: SourceKind
    media_type: MediaType
    text: str


@dataclass(frozen=True)
class DocumentView:
    id: UUID
    title: str
    source_kind: str
    media_type: str
    status: str  # pending | ready | failed | withdrawn | stale (computed, AC-7)
    failure_code: str | None
    chunk_count: int
    created_at: datetime


@dataclass(frozen=True)
class KnowledgeHit:
    document_id: UUID
    title: str
    heading_path: str
    position: int
    text: str
    score: float


def _firm(ctx: AuthContext) -> Resource:
    return Resource.firm(ctx.tenant_id)


async def add_document(ctx: AuthContext, new: NewDocument) -> UUID:
    """Store the document (`pending`) and its chunks; the embedding workflow follows (AC-1)."""
    await authorise(ctx, "knowledge.manage", _firm(ctx))
    s = settings()
    if "\x00" in new.text or not new.text.strip():
        raise KnowledgeEmpty("no text")
    if len(new.text.encode()) > s.knowledge_max_bytes:
        raise KnowledgeTooLarge("document too large")
    chunks = chunk_document(new.text, markdown=new.media_type == "text/markdown")
    if not chunks:
        raise KnowledgeEmpty("no text")
    if len(chunks) > s.knowledge_max_chunks_per_document:
        raise KnowledgeTooLarge("too many chunks")
    fingerprint = hashlib.sha256(new.text.encode()).hexdigest()
    document_id = uuid4()
    async with uow(ctx.tenant) as tx:
        if await active_document_with(tx.session, fingerprint) is not None:
            raise KnowledgeDuplicate(fingerprint)
        if await firm_chunk_count(tx.session) + len(chunks) > s.knowledge_max_chunks_per_firm:
            raise KnowledgeTooLarge("firm limit")
        await insert_document(
            tx.session,
            {
                "id": document_id,
                "tenant_id": ctx.tenant_id,
                "title": new.title,
                "source_kind": new.source_kind,
                "media_type": new.media_type,
                "fingerprint": fingerprint,
                "char_count": len(new.text),
                "added_by": ctx.user_id,
            },
        )
        await insert_chunks(
            tx.session,
            [
                {
                    "tenant_id": ctx.tenant_id,
                    "document_id": document_id,
                    "position": c.position,
                    "heading_path": c.heading_path,
                    "text": c.text,
                    "char_count": len(c.text),
                }
                for c in chunks
            ],
        )
        tx.record(
            "knowledge_document.added",
            target=Target("knowledge_document", document_id),
            after=Ref(source_fingerprint=fingerprint, chunks=len(chunks)),
        )
        tx.emit(KnowledgeDocumentAdded(document_id=document_id))
    return document_id


async def withdraw_document(ctx: AuthContext, document_id: UUID) -> None:
    """Excluded from search from now on (AC-4)."""
    await authorise(ctx, "knowledge.manage", _firm(ctx))
    async with uow(ctx.tenant) as tx:
        document = await lock_document(tx.session, document_id)
        if document is None:
            raise NotFound("knowledge_document")
        if document.status == "withdrawn":
            raise KnowledgeWithdrawn(str(document_id))
        await set_document_status(tx.session, document_id, "withdrawn", withdrawn=True)
        tx.record(
            "knowledge_document.withdrawn",
            target=Target("knowledge_document", document_id),
            after=Ref(user_id=ctx.user_id),
        )


async def documents(ctx: AuthContext) -> list[DocumentView]:
    await authorise(ctx, "knowledge.read", _firm(ctx))
    model = settings().embedding_model
    async with tenant_session(ctx.tenant) as session:
        rows = await list_documents(session, model)
    return [_view(d, total, on_model) for d, total, on_model in rows]


async def document(ctx: AuthContext, document_id: UUID) -> DocumentView:
    await authorise(ctx, "knowledge.read", _firm(ctx))
    views = [v for v in await documents(ctx) if v.id == document_id]
    if not views:
        raise NotFound("knowledge_document")
    return views[0]


def _view(d: KnowledgeDocument, total: int, on_model: int) -> DocumentView:
    # Ready, but every chunk embedded by another model: excluded from search until re-embedded.
    stale = d.status == "ready" and total > 0 and on_model == 0
    return DocumentView(
        d.id,
        d.title,
        d.source_kind,
        d.media_type,
        "stale" if stale else d.status,
        d.failure_code,
        total,
        d.created_at,
    )


async def search_knowledge(ctx: AuthContext, query: str, k: int = 8) -> list[KnowledgeHit]:
    """The firm's `k` nearest ready chunks to the query, best first (AC-8, AC-9)."""
    await authorise(ctx, "knowledge.read", _firm(ctx))
    query = query.strip()
    if not query or len(query) > MAX_QUERY_CHARS or not 1 <= k <= MAX_K:
        raise KnowledgeQueryInvalid("query")
    embedded = await embed(
        EmbedCall(
            purpose="knowledge search",
            texts=(query,),
            attribution=Attribution(ctx.tenant, None, SEARCHER, None),
            work_class="interactive",
            essential=False,
            budget_usd=_QUERY_BUDGET,
        )
    )
    async with tenant_session(ctx.tenant) as session:
        rows = await nearest_chunks(session, ctx.tenant_id, embedded.vectors[0], embedded.model, k)
    _log.info("knowledge.search", k=k, results=len(rows))
    return [
        KnowledgeHit(c.document_id, title, c.heading_path, c.position, c.text, 1.0 - distance)
        for c, title, distance in rows
    ]


def knowledge_context(hits: list[KnowledgeHit]) -> str:
    """Retrieved chunks as untrusted, delimited text for a context layer (AC-10; ADR-052).
    JSON-encoded with `<` escaped, so chunk text can't open or close a delimiter."""
    blocks: list[str] = []
    for hit in hits:
        body = json.dumps(
            {"title": hit.title, "section": hit.heading_path, "text": hit.text},
            ensure_ascii=False,
        ).replace("<", "\\u003c")
        blocks.append(
            f'<untrusted name="knowledge" document="{hit.document_id}" '
            f'position="{hit.position}" classification="internal">\n{body}\n</untrusted>'
        )
    return "\n".join(blocks)


# --- The embedding workflow's steps (TASK-024 design §7) ---------------------------------------


def _system(tenant_id: UUID, document_id: UUID) -> TenantContext:
    return TenantContext(tenant_id, "system", f"knowledge:{document_id}")


async def embed_next_batch(tenant_id: UUID, document_id: UUID) -> BatchOutcome:
    """Embed up to 64 chunks still without a vector; ready when none remain (AC-6). Resuming is
    natural: only chunks without vectors are taken, and each is written once."""
    tenant = _system(tenant_id, document_id)
    async with tenant_session(tenant) as session:
        found = await get_document(session, document_id)
        if found is None or found.status != "pending":
            return BatchOutcome(done=True)
        chunks = await chunks_without_vectors(session, document_id, BATCH)
    if chunks:
        try:
            result = await embed(
                EmbedCall(
                    purpose="knowledge ingestion",
                    texts=tuple(c.text for c in chunks),
                    attribution=Attribution(tenant, None, EMBEDDER, None),
                    work_class="batch",
                    essential=False,
                    budget_usd=_BATCH_BUDGET,
                )
            )
        except NotAdmitted as waiting:
            return BatchOutcome(done=False, wait_seconds=max(1, waiting.retry_after))
        except (BudgetExceeded, BudgetExhausted, EmbedTooLarge) as refused:
            if isinstance(refused, BudgetExceeded):
                code = "budget_exceeded"
            elif isinstance(refused, BudgetExhausted):
                code = "budget_exhausted"
            else:
                code = "embed_refused"
            await fail_document(tenant_id, document_id, code)
            return BatchOutcome(done=True)
        vectors = {c.position: v for c, v in zip(chunks, result.vectors, strict=True)}
        async with uow(tenant) as tx:
            if (await lock_document(tx.session, document_id)) is None:
                raise NotFound("knowledge_document")
            written = await store_vectors(tx.session, document_id, vectors, result.model)
            tx.record(
                "knowledge_chunk.embedded",
                target=Target("knowledge_document", document_id),
                after=Ref(chunks=written),
            )
        _log.info("knowledge.embed_batch", document_id=document_id, chunks=written)
    async with tenant_session(tenant) as session:
        if await remaining_chunks(session, document_id) > 0:
            return BatchOutcome(done=False)
    try:
        async with uow(tenant) as tx:
            document_row = await lock_document(tx.session, document_id)
            if document_row is not None and document_row.status == "pending":
                await set_document_status(tx.session, document_id, "ready")
                tx.record(
                    "knowledge_document.ready", target=Target("knowledge_document", document_id)
                )
    except MissingAuditEvent:
        pass  # withdrawn or failed meanwhile: nothing to commit
    return BatchOutcome(done=True)


async def fail_document(tenant_id: UUID, document_id: UUID, code: str) -> None:
    """`failed` with a fixed code, unless it is no longer pending (withdrawn meanwhile)."""
    async with uow(_system(tenant_id, document_id)) as tx:
        found = await lock_document(tx.session, document_id)
        if found is not None and found.status == "pending":
            await set_document_status(tx.session, document_id, "failed", failure_code=code)
        tx.record("knowledge_document.failed", target=Target("knowledge_document", document_id))
