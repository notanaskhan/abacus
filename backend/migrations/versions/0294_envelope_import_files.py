"""Record-mode import's staged files (N-02-T08; N-02 §3.1; DEC-818).

`envelope_import_files`: one file a person uploaded for a record-mode import (the completed
document, the provider's certificate), scanned before storage and kept encrypted in the evidence
bucket under its SHA-256. `POST /v1/envelopes/import` names them by id; the import consumes each
once (`consumed_envelope_id`, set once). Only the uploader's own unconsumed files are usable (the
service's check). `file_name` is Confidential; the rest Internal.

Revision ID: 0294
Revises: 0293
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0294"
down_revision = "0293"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE envelope_import_files (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            uploaded_by uuid NOT NULL,
            file_name text NOT NULL CHECK (char_length(file_name) BETWEEN 1 AND 255),
            media_type text NOT NULL CHECK (char_length(media_type) BETWEEN 3 AND 100),
            size_bytes bigint NOT NULL CHECK (size_bytes > 0),
            sha256 text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
            storage_key text NOT NULL CHECK (char_length(storage_key) BETWEEN 1 AND 512),
            storage_version_id text NOT NULL CHECK (char_length(storage_version_id) <= 200),
            consumed_envelope_id uuid NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, uploaded_by) REFERENCES memberships (tenant_id, user_id),
            FOREIGN KEY (tenant_id, consumed_envelope_id) REFERENCES envelopes (tenant_id, id)
        )
        """
    )
    tenant_table(op, "envelope_import_files")
    op.execute("REVOKE UPDATE, DELETE ON envelope_import_files FROM abacus_app")
    insert_columns(
        op,
        "envelope_import_files",
        (
            "id",
            "tenant_id",
            "uploaded_by",
            "file_name",
            "media_type",
            "size_bytes",
            "sha256",
            "storage_key",
            "storage_version_id",
        ),
    )
    op.execute("GRANT UPDATE (consumed_envelope_id) ON envelope_import_files TO abacus_app")
    op.execute(
        """
        CREATE FUNCTION envelope_import_files_consumed_once() RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = pg_catalog, public, pg_temp
        AS $$
        BEGIN
            IF OLD.consumed_envelope_id IS NOT NULL THEN
                RAISE EXCEPTION 'an import file is consumed once'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER envelope_import_files_consumed_once BEFORE UPDATE ON envelope_import_files "
        "FOR EACH ROW EXECUTE FUNCTION envelope_import_files_consumed_once()"
    )


def downgrade() -> None:
    op.execute("DROP TABLE envelope_import_files")
    op.execute("DROP FUNCTION envelope_import_files_consumed_once()")
