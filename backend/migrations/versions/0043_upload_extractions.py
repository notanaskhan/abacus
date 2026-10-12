"""Upload extractions (SPEC-029; TASK-054; ADR-110).

`upload_extractions`: what code read from an uploaded file, for one evidence version or inbox
file and one extractor version. A derived record: it never alters the evidence and can be
rebuilt. The full text and tables are a JSON object in storage (content-addressed); the fields
checks need are columns. Insert-only.

Revision ID: 0043
Revises: 0042
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0043"
down_revision = "0042"
branch_labels = None
depends_on = None

_INSERT = (
    "tenant_id",
    "engagement_id",
    "evidence_version_id",
    "inbox_file_id",
    "extractor_version",
    "status",
    "reason",
    "page_count",
    "truncated",
    "storage_key",
    "storage_version_id",
    "fingerprint",
    "size_bytes",
    "period_start",
    "period_end",
    "as_of",
    "entity_name",
    "account_last4",
    "opening",
    "closing",
    "credits",
    "debits",
    "grand_total",
)


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE upload_extractions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            evidence_version_id uuid NULL,
            inbox_file_id uuid NULL,
            extractor_version text NOT NULL CHECK (extractor_version ~ '^v[0-9]{1,4}$'),
            status text NOT NULL CHECK (status IN ('extracted', 'unreadable', 'not_extracted')),
            reason text NULL CHECK (reason ~ '^[a-z][a-z_]{0,39}$'),
            page_count integer NULL CHECK (page_count >= 0),
            truncated boolean NOT NULL DEFAULT false,
            storage_key text NULL CHECK (length(storage_key) BETWEEN 1 AND 300),
            storage_version_id text NULL CHECK (length(storage_version_id) BETWEEN 1 AND 200),
            fingerprint text NULL CHECK (fingerprint ~ '^[0-9a-f]{64}$'),
            size_bytes bigint NULL CHECK (size_bytes > 0),
            period_start date NULL,
            period_end date NULL,
            as_of date NULL,
            entity_name text NULL CHECK (length(entity_name) BETWEEN 1 AND 200),
            account_last4 text NULL CHECK (account_last4 ~ '^[0-9]{4}$'),
            opening numeric(20, 2) NULL,
            closing numeric(20, 2) NULL,
            credits numeric(20, 2) NULL,
            debits numeric(20, 2) NULL,
            grand_total numeric(20, 2) NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id),
            FOREIGN KEY (tenant_id, evidence_version_id)
                REFERENCES evidence_versions (tenant_id, id),
            FOREIGN KEY (tenant_id, inbox_file_id) REFERENCES inbox_files (tenant_id, id),
            CHECK ((evidence_version_id IS NULL) <> (inbox_file_id IS NULL)),
            CHECK ((storage_key IS NULL) = (fingerprint IS NULL)),
            CHECK (status = 'extracted' OR storage_key IS NULL)
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX upload_extractions_one_per_version ON upload_extractions "
        "(tenant_id, evidence_version_id, extractor_version) WHERE evidence_version_id IS NOT NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX upload_extractions_one_per_inbox_file ON upload_extractions "
        "(tenant_id, inbox_file_id, extractor_version) WHERE inbox_file_id IS NOT NULL"
    )
    tenant_table(op, "upload_extractions")
    op.execute("REVOKE UPDATE, DELETE ON upload_extractions FROM abacus_app")
    insert_columns(op, "upload_extractions", _INSERT)


def downgrade() -> None:
    op.execute("DROP TABLE upload_extractions")
