"""Knowledge documents and chunks for vector recall (SPEC-009; ADR-053, ADR-056).

A firm's methodology documents, split into attributed chunks, each embedded by one model through
the gateway. No ANN index (Q1): search is exact over the firm's own chunks, so no index is shared
across tenants (ADR-053). Vectors are written once per chunk (null to value) by the embedding
workflow; documents change only status (pending, ready, failed, withdrawn).

Revision ID: 0020
Revises: 0019
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(
        """
        CREATE TABLE knowledge_documents (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            title text NOT NULL CHECK (length(title) BETWEEN 1 AND 200),
            source_kind text NOT NULL CHECK (source_kind IN ('firm_own', 'public')),
            media_type text NOT NULL CHECK (media_type IN ('text/plain', 'text/markdown')),
            fingerprint text NOT NULL CHECK (fingerprint ~ '^[0-9a-f]{64}$'),
            char_count integer NOT NULL CHECK (char_count > 0),
            status text NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'ready', 'failed', 'withdrawn')),
            failure_code text CHECK (length(failure_code) BETWEEN 1 AND 50),
            added_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            withdrawn_at timestamptz,
            UNIQUE (tenant_id, id),
            CONSTRAINT knowledge_documents_withdrawn
                CHECK ((status = 'withdrawn') = (withdrawn_at IS NOT NULL)),
            FOREIGN KEY (tenant_id, added_by) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX knowledge_documents_once ON knowledge_documents "
        "(tenant_id, fingerprint) WHERE status <> 'withdrawn'"
    )
    op.execute(
        """
        CREATE TABLE knowledge_chunks (
            tenant_id uuid NOT NULL,
            document_id uuid NOT NULL,
            position integer NOT NULL CHECK (position >= 0),
            heading_path text NOT NULL CHECK (length(heading_path) <= 1000),
            text text NOT NULL CHECK (length(text) BETWEEN 1 AND 2000),
            char_count integer NOT NULL CHECK (char_count > 0),
            embedding vector(1024),
            embedding_model text CHECK (length(embedding_model) BETWEEN 1 AND 100),
            embedded_at timestamptz,
            PRIMARY KEY (tenant_id, document_id, position),
            CONSTRAINT knowledge_chunks_embedded CHECK (
                (embedding IS NULL) = (embedding_model IS NULL)
                AND (embedding IS NULL) = (embedded_at IS NULL)
            ),
            FOREIGN KEY (tenant_id, document_id) REFERENCES knowledge_documents (tenant_id, id)
        )
        """
    )
    for table in ("knowledge_documents", "knowledge_chunks"):
        tenant_table(op, table)
    op.execute("REVOKE UPDATE, DELETE ON knowledge_documents, knowledge_chunks FROM abacus_app")
    insert_columns(
        op,
        "knowledge_documents",
        (
            "id",
            "tenant_id",
            "title",
            "source_kind",
            "media_type",
            "fingerprint",
            "char_count",
            "added_by",
        ),
    )
    insert_columns(
        op,
        "knowledge_chunks",
        ("tenant_id", "document_id", "position", "heading_path", "text", "char_count"),
    )
    op.execute(
        "GRANT UPDATE (status, failure_code, withdrawn_at) ON knowledge_documents TO abacus_app"
    )
    op.execute(
        "GRANT UPDATE (embedding, embedding_model, embedded_at) ON knowledge_chunks TO abacus_app"
    )


def downgrade() -> None:
    op.execute("DROP TABLE knowledge_chunks")
    op.execute("DROP TABLE knowledge_documents")
