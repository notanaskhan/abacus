"""Uploads on the client's behalf and the engagement inbox (SPEC-023; TASK-039).

`evidence_versions.upload_note`: where a file the firm added for the client came from, written
once at insert (D1; the table stays immutable). `inbox_files`: files dropped at the engagement
level, waiting for a person to assign each to a request item (or discard it).

Revision ID: 0031
Revises: 0030
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None

_DECISION = "status, assigned_item_id, assigned_version_id, decided_by, decided_at"


def upgrade() -> None:
    op.execute(
        "ALTER TABLE evidence_versions ADD COLUMN upload_note text NULL "
        "CHECK (length(upload_note) BETWEEN 1 AND 500)"
    )
    op.execute("GRANT INSERT (upload_note) ON evidence_versions TO abacus_app")
    op.execute(
        """
        CREATE TABLE inbox_files (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            file_name text NOT NULL CHECK (length(file_name) BETWEEN 1 AND 200),
            media_type text NOT NULL CHECK (length(media_type) BETWEEN 1 AND 100),
            size_bytes bigint NOT NULL CHECK (size_bytes > 0),
            fingerprint text NOT NULL CHECK (fingerprint ~ '^[0-9a-f]{64}$'),
            storage_key text NOT NULL CHECK (length(storage_key) BETWEEN 1 AND 300),
            storage_version_id text NOT NULL CHECK (length(storage_version_id) BETWEEN 1 AND 200),
            uploaded_by uuid NOT NULL,
            uploaded_by_staff boolean NOT NULL,
            note text NULL CHECK (length(note) BETWEEN 1 AND 500),
            status text NOT NULL DEFAULT 'waiting'
                CHECK (status IN ('waiting', 'assigned', 'discarded')),
            assigned_item_id uuid NULL,
            assigned_version_id uuid NULL,
            decided_by uuid NULL,
            decided_at timestamptz NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id),
            FOREIGN KEY (tenant_id, uploaded_by) REFERENCES memberships (tenant_id, user_id),
            CHECK ((status = 'assigned') = (assigned_version_id IS NOT NULL)),
            CHECK ((status = 'waiting') = (decided_at IS NULL))
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX inbox_files_one_waiting ON inbox_files "
        "(tenant_id, engagement_id, fingerprint) WHERE status = 'waiting'"
    )
    tenant_table(op, "inbox_files")
    op.execute("REVOKE UPDATE, DELETE ON inbox_files FROM abacus_app")
    insert_columns(
        op,
        "inbox_files",
        (
            "tenant_id",
            "engagement_id",
            "file_name",
            "media_type",
            "size_bytes",
            "fingerprint",
            "storage_key",
            "storage_version_id",
            "uploaded_by",
            "uploaded_by_staff",
            "note",
        ),
    )
    op.execute(f"GRANT UPDATE ({_DECISION}) ON inbox_files TO abacus_app")


def downgrade() -> None:
    op.execute("DROP TABLE inbox_files")
    op.execute("REVOKE INSERT (upload_note) ON evidence_versions FROM abacus_app")
    op.execute("ALTER TABLE evidence_versions DROP COLUMN upload_note")
