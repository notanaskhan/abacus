"""A rendered file recorded against its generated-document version (P-11-T09; DEC-1457).

Kept apart from `documents.py` so the renderer API (`api.py`), which every consumer imports, does
not import `evidence.api`: the render workflow's activity (P-11-T11) calls `record_file`, and a
consumer such as `engagements` reaches `reporting.api` without a cycle back through `evidence`.
"""

from __future__ import annotations

from typing import Literal, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import transaction_context
from abacus.kernel.uow import UnitOfWork
from abacus.modules.evidence.api import GeneratedFile, StoredObject, record_generated
from abacus.modules.reporting.documents import document_row


async def record_file(
    tx: UnitOfWork,
    *,
    document_id: UUID,
    version_no: int,
    file_format: Literal["pdf", "docx"],
    stored: StoredObject,
    render_hash: str,
    page_count: int,
    title: str,
    requested_by: UUID | None,
) -> UUID:
    """The version's rendered bytes as an evidence version and its `generated_document_files`
    row, in the caller's unit of work; the render job succeeds. The bytes were stored before the
    unit of work (`evidence.api.store_generated`, Object Lock), and the evidence fingerprint must
    equal the render hash; nothing rewrites them."""
    doc = await document_row(tx, document_id)
    if doc is None:
        raise LookupError("generated document not found")
    version_id = await tx.session.scalar(
        text(
            "SELECT id FROM generated_document_versions WHERE generated_document_id = :d "
            "AND version_no = :n"
        ),
        {"d": document_id, "n": version_no},
    )
    if version_id is None:
        raise LookupError("generated document version not found")
    tenant_id = (await transaction_context(tx.session)).tenant_id
    media = (
        "application/pdf"
        if file_format == "pdf"
        else ("application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    )
    evidence_version_id = await record_generated(
        tx,
        tenant_id=tenant_id,
        client_id=cast(UUID, doc["client_id"]),
        engagement_id=cast(UUID | None, doc["engagement_id"]),
        work_item_id=cast(UUID | None, doc["work_item_id"]),
        file=GeneratedFile(
            stored=stored,
            render_hash=render_hash,
            media_type=media,
            title=title,
            provenance=f"generated:{doc['kind']}:v{version_no}",
        ),
        requested_by=requested_by,
    )
    await tx.session.execute(
        text(
            "INSERT INTO generated_document_files (tenant_id, version_id, format, "
            "evidence_version_id, render_hash, page_count, byte_size) VALUES "
            "(:t, :v, :f, :e, :h, :p, :b)"
        ),
        {
            "t": tenant_id,
            "v": version_id,
            "f": file_format,
            "e": evidence_version_id,
            "h": bytes.fromhex(render_hash),
            "p": page_count,
            "b": stored.size,
        },
    )
    await tx.session.execute(
        text(
            "UPDATE render_jobs SET status = 'succeeded', finished_at = clock_timestamp() "
            "WHERE generated_document_id = :d AND target_version_no = :n"
        ),
        {"d": document_id, "n": version_no},
    )
    return evidence_version_id
