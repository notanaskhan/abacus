"""Upload previews (SPEC-029 goal 8; TASK-056; ADR-110).

`upload_previews`: per evidence version or inbox file, what the viewer shows: page images
(`pages`, a PDF), one image (`image`), the extraction's tables (`table`), or nothing (`none`, with
why). `upload_preview_pages`: the server-made PNGs, content-addressed in storage. The browser never
renders the raw file. Both insert-only.

Revision ID: 0045
Revises: 0044
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0045"
down_revision = "0044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE upload_previews (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            evidence_version_id uuid NULL,
            inbox_file_id uuid NULL,
            renderer_version text NOT NULL CHECK (renderer_version ~ '^v[0-9]{1,4}$'),
            kind text NOT NULL CHECK (kind IN ('pages', 'image', 'table', 'none')),
            reason text NULL CHECK (reason ~ '^[a-z][a-z_]{0,39}$'),
            page_count integer NOT NULL DEFAULT 0 CHECK (page_count BETWEEN 0 AND 50),
            truncated boolean NOT NULL DEFAULT false,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id),
            FOREIGN KEY (tenant_id, evidence_version_id)
                REFERENCES evidence_versions (tenant_id, id),
            FOREIGN KEY (tenant_id, inbox_file_id) REFERENCES inbox_files (tenant_id, id),
            CHECK ((evidence_version_id IS NULL) <> (inbox_file_id IS NULL))
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX upload_previews_one_per_version ON upload_previews "
        "(tenant_id, evidence_version_id, renderer_version) WHERE evidence_version_id IS NOT NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX upload_previews_one_per_inbox_file ON upload_previews "
        "(tenant_id, inbox_file_id, renderer_version) WHERE inbox_file_id IS NOT NULL"
    )
    op.execute(
        """
        CREATE TABLE upload_preview_pages (
            tenant_id uuid NOT NULL,
            preview_id uuid NOT NULL,
            page_no integer NOT NULL CHECK (page_no BETWEEN 1 AND 50),
            storage_key text NOT NULL CHECK (length(storage_key) BETWEEN 1 AND 300),
            storage_version_id text NOT NULL CHECK (length(storage_version_id) BETWEEN 1 AND 200),
            fingerprint text NOT NULL CHECK (fingerprint ~ '^[0-9a-f]{64}$'),
            size_bytes bigint NOT NULL CHECK (size_bytes > 0),
            width integer NOT NULL CHECK (width BETWEEN 1 AND 4000),
            height integer NOT NULL CHECK (height BETWEEN 1 AND 8000),
            PRIMARY KEY (tenant_id, preview_id, page_no),
            FOREIGN KEY (tenant_id, preview_id) REFERENCES upload_previews (tenant_id, id)
        )
        """
    )
    for table in ("upload_previews", "upload_preview_pages"):
        tenant_table(op, table)
        op.execute(f"REVOKE UPDATE, DELETE ON {table} FROM abacus_app")
    insert_columns(
        op,
        "upload_previews",
        (
            "tenant_id",
            "engagement_id",
            "evidence_version_id",
            "inbox_file_id",
            "renderer_version",
            "kind",
            "reason",
            "page_count",
            "truncated",
        ),
    )
    insert_columns(
        op,
        "upload_preview_pages",
        (
            "tenant_id",
            "preview_id",
            "page_no",
            "storage_key",
            "storage_version_id",
            "fingerprint",
            "size_bytes",
            "width",
            "height",
        ),
    )


def downgrade() -> None:
    op.execute("DROP TABLE upload_preview_pages")
    op.execute("DROP TABLE upload_previews")
