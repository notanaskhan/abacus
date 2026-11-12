"""The search index's writes (P-02-T06; ADR-241 decisions 3 and 8; DEC-4612). PROTECTED.

`search_documents` is an upserted, rebuildable projection of the owners' current state and
`search_recents` is a person's operational UI state: neither is a record, so their writes commit on
their own connection with no audit event, on the precedent of `kernel/slots.py` and the audit label
index (`audit_trail/labels.py`, DEC-436). UOW-001 and UOW-002 exempt this file only. What is
audited is the reindex itself (`search_index.reindex_requested`, `.reindex_completed`, through the
unit of work in `indexer.py`).

Every statement is tenant-scoped through `tenant_connection` (RLS forced on both tables). A
document's `tsv` is written in the same upsert: title A · identifiers B · related names C · context
D, configuration `simple` (ADR-241 decision 5).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from typing import Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_connection
from abacus.modules.platform.search.spec import SearchIndexDocument, SearchProjection

ACTOR: Final = "system:search_indexer"

_UPSERT = text(
    """
    INSERT INTO search_documents (
        tenant_id, object_type, object_id, group_key, scope_kind, engagement_id, work_item_id,
        client_id, owner_user_id, data_class, title, context, identifiers_text, related,
        related_text, status_code, status_context, due_on, tag, use_count, target_params, tsv,
        source_updated_at, indexed_at
    ) VALUES (
        :tenant_id, :object_type, :object_id, :group_key, :scope_kind, :engagement_id,
        :work_item_id, :client_id, :owner_user_id, :data_class, :title, :context,
        :identifiers_text, CAST(:related AS jsonb), :related_text, :status_code, :status_context,
        :due_on, :tag, :use_count, CAST(:target_params AS jsonb),
        setweight(to_tsvector('simple', :title), 'A')
          || setweight(to_tsvector('simple', :identifiers_text), 'B')
          || setweight(to_tsvector('simple', :related_text), 'C')
          || setweight(to_tsvector('simple', coalesce(:context, '')), 'D'),
        :source_updated_at, clock_timestamp()
    )
    ON CONFLICT (tenant_id, object_type, object_id) DO UPDATE SET
        group_key = EXCLUDED.group_key, scope_kind = EXCLUDED.scope_kind,
        engagement_id = EXCLUDED.engagement_id, work_item_id = EXCLUDED.work_item_id,
        client_id = EXCLUDED.client_id, owner_user_id = EXCLUDED.owner_user_id,
        data_class = EXCLUDED.data_class, title = EXCLUDED.title, context = EXCLUDED.context,
        identifiers_text = EXCLUDED.identifiers_text, related = EXCLUDED.related,
        related_text = EXCLUDED.related_text, status_code = EXCLUDED.status_code,
        status_context = EXCLUDED.status_context, due_on = EXCLUDED.due_on, tag = EXCLUDED.tag,
        use_count = EXCLUDED.use_count, target_params = EXCLUDED.target_params,
        tsv = EXCLUDED.tsv, source_updated_at = EXCLUDED.source_updated_at,
        indexed_at = clock_timestamp()
    """
)
_DELETE = text(
    "DELETE FROM search_documents WHERE object_type = :object_type AND object_id = :object_id"
)


def _indexer(tenant_id: UUID) -> TenantContext:
    return TenantContext(tenant_id, "system", ACTOR)


def row_of(projection: SearchProjection, doc: SearchIndexDocument) -> dict[str, object]:
    """The document as the upsert's parameters (and the drift check's hash input)."""
    return {
        "object_type": projection.object_type,
        "object_id": doc.object_id,
        "group_key": projection.group,
        "scope_kind": projection.scope_kind,
        "engagement_id": doc.engagement_id,
        "work_item_id": doc.work_item_id,
        "client_id": doc.client_id,
        "owner_user_id": doc.owner_user_id,
        "data_class": projection.data_class,
        "title": doc.title,
        "context": doc.context,
        "identifiers_text": " ".join(doc.identifiers),
        "related": json.dumps([{"name": r.name, "label": r.label} for r in doc.related]),
        "related_text": " ".join(r.name for r in doc.related),
        "status_code": doc.status_code,
        "status_context": doc.status_context,
        "due_on": doc.due_on,
        "tag": doc.tag,
        "use_count": doc.use_count,
        "target_params": json.dumps(dict(sorted(doc.target_params.items()))),
        "source_updated_at": doc.source_updated_at,
    }


def document_hash(projection: SearchProjection, doc: SearchIndexDocument) -> str:
    """A canonical hash of what the builder would store (the drift check compares it)."""
    row = {k: str(v) if v is not None else None for k, v in row_of(projection, doc).items()}
    return hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest()


async def upsert(tenant_id: UUID, projection: SearchProjection, doc: SearchIndexDocument) -> None:
    async with tenant_connection(_indexer(tenant_id)) as conn:
        await conn.execute(_UPSERT, {"tenant_id": tenant_id, **row_of(projection, doc)})
        await conn.commit()


async def delete(tenant_id: UUID, object_type: str, object_id: UUID) -> bool:
    async with tenant_connection(_indexer(tenant_id)) as conn:
        gone = await conn.execute(_DELETE, {"object_type": object_type, "object_id": object_id})
        await conn.commit()
        return (gone.rowcount or 0) > 0


async def indexed_ids(
    tenant_id: UUID, object_type: str, after: UUID | None, limit: int
) -> list[UUID]:
    """A page of the ids already indexed for a type (a reindex of a type with no lister)."""
    async with tenant_connection(_indexer(tenant_id)) as conn:
        rows = await conn.execute(
            text(
                "SELECT object_id FROM search_documents WHERE object_type = :t "
                "AND (CAST(:after AS uuid) IS NULL OR object_id > CAST(:after AS uuid)) "
                "ORDER BY object_id LIMIT :limit"
            ),
            {"t": object_type, "after": after, "limit": limit},
        )
        return [UUID(str(r[0])) for r in rows]


async def indexed_ids_for_client(
    tenant_id: UUID, object_type: str, client_id: UUID, after: UUID | None, limit: int
) -> list[UUID]:
    """A page of one client's indexed ids for a type (a client rename's fan-out reindex)."""
    async with tenant_connection(_indexer(tenant_id)) as conn:
        rows = await conn.execute(
            text(
                "SELECT object_id FROM search_documents WHERE object_type = :t "
                "AND client_id = :c "
                "AND (CAST(:after AS uuid) IS NULL OR object_id > CAST(:after AS uuid)) "
                "ORDER BY object_id LIMIT :limit"
            ),
            {"t": object_type, "c": client_id, "after": after, "limit": limit},
        )
        return [UUID(str(r[0])) for r in rows]


async def sample(tenant_id: UUID, object_type: str, n: int) -> list[UUID]:
    """Up to `n` random indexed ids of a type (the nightly drift check's 1 %)."""
    async with tenant_connection(_indexer(tenant_id)) as conn:
        rows = await conn.execute(
            text(
                "SELECT object_id FROM search_documents WHERE object_type = :t "
                "ORDER BY random() LIMIT :n"
            ),
            {"t": object_type, "n": n},
        )
        return [UUID(str(r[0])) for r in rows]


async def count(tenant_id: UUID, object_type: str) -> int:
    async with tenant_connection(_indexer(tenant_id)) as conn:
        found = await conn.execute(
            text("SELECT count(*) FROM search_documents WHERE object_type = :t"),
            {"t": object_type},
        )
        return int(found.scalar_one())


async def stored_hash(
    tenant_id: UUID, projection: SearchProjection, object_id: UUID
) -> str | None:
    """The stored row's hash in `document_hash`'s terms, or None when it is not indexed."""
    async with tenant_connection(_indexer(tenant_id)) as conn:
        found = await conn.execute(
            text(
                "SELECT engagement_id, work_item_id, client_id, owner_user_id, data_class, title, "
                "context, identifiers_text, related, related_text, status_code, status_context, "
                "due_on, tag, use_count, target_params, source_updated_at, group_key, scope_kind "
                "FROM search_documents WHERE object_type = :t AND object_id = :id"
            ),
            {"t": projection.object_type, "id": object_id},
        )
        r = found.mappings().first()
    if r is None:
        return None
    row = {
        "object_type": projection.object_type,
        "object_id": object_id,
        **{k: r[k] for k in ("group_key", "scope_kind", "engagement_id", "work_item_id")},
        **{k: r[k] for k in ("client_id", "owner_user_id", "data_class", "title", "context")},
        "identifiers_text": r["identifiers_text"],
        "related": json.dumps(r["related"]),
        "related_text": r["related_text"],
        **{k: r[k] for k in ("status_code", "status_context", "due_on", "tag", "use_count")},
        "target_params": json.dumps(dict(sorted(dict(r["target_params"]).items()))),
        "source_updated_at": r["source_updated_at"],
    }
    flat = {k: str(v) if v is not None else None for k, v in row.items()}
    return hashlib.sha256(json.dumps(flat, sort_keys=True).encode()).hexdigest()


async def record_recent(
    tenant_id: UUID, user_id: UUID, object_type: str, object_id: UUID, keep: int
) -> None:
    """The person opened a record they may read: first in their recents, trimmed to `keep`."""
    async with tenant_connection(_indexer(tenant_id)) as conn:
        await conn.execute(
            text(
                "INSERT INTO search_recents (tenant_id, user_id, object_type, object_id) "
                "VALUES (:t, :u, :ot, :oi) "
                "ON CONFLICT (tenant_id, user_id, object_type, object_id) "
                "DO UPDATE SET opened_at = clock_timestamp()"
            ),
            {"t": tenant_id, "u": user_id, "ot": object_type, "oi": object_id},
        )
        await conn.execute(
            text(
                "DELETE FROM search_recents WHERE user_id = :u "
                "AND (object_type, object_id) NOT IN "
                "(SELECT object_type, object_id FROM search_recents WHERE user_id = :u "
                "ORDER BY opened_at DESC LIMIT :keep)"
            ),
            {"u": user_id, "keep": keep},
        )
        await conn.commit()


async def purge_recents(tenant_id: UUID, user_ids: Sequence[UUID]) -> int:
    """A deactivated member's recents go (P-02 §4.6 `membership.revoked`)."""
    if not user_ids:
        return 0
    async with tenant_connection(_indexer(tenant_id)) as conn:
        gone = await conn.execute(
            text("DELETE FROM search_recents WHERE user_id = ANY(CAST(:ids AS uuid[]))"),
            {"ids": [str(u) for u in user_ids]},
        )
        await conn.commit()
        return gone.rowcount or 0


async def purge_tenant(tenant_id: UUID) -> int:
    """Offboarding: every index row and every recent of the firm go (P-02-T06 acceptance)."""
    async with tenant_connection(_indexer(tenant_id)) as conn:
        docs = await conn.execute(text("DELETE FROM search_documents"))
        recents = await conn.execute(text("DELETE FROM search_recents"))
        await conn.commit()
        return (docs.rowcount or 0) + (recents.rowcount or 0)
