"""Evidence items and versions (ADR-004, ADR-016, ADR-104; TASK-009 design §4).

Evidence versions are insert-only for the app (no UPDATE or DELETE privilege, column-limited
INSERT) and, as a second layer, a trigger rejects UPDATE, DELETE and TRUNCATE for every role,
owner included (AC-13). A version's storage key is derived from its tenant and fingerprint, so a
row can only point at its own tenant's content-addressed object.

Revision ID: 0007
Revises: 0006
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE evidence_items (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            title text NOT NULL CHECK (length(title) BETWEEN 1 AND 200),
            created_by_kind text NOT NULL
                CHECK (created_by_kind IN ('human', 'agent', 'system')),
            created_by_id text NOT NULL CHECK (length(created_by_id) BETWEEN 1 AND 200),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, engagement_id, id),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE evidence_versions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            evidence_item_id uuid NOT NULL,
            version_no integer NOT NULL CHECK (version_no >= 1),
            fingerprint text NOT NULL CHECK (fingerprint ~ '^[0-9a-f]{64}$'),
            storage_key text NOT NULL,
            storage_version_id text NOT NULL
                CHECK (length(storage_version_id) BETWEEN 1 AND 200),
            size_bytes bigint NOT NULL CHECK (size_bytes >= 0),
            media_type text NOT NULL CHECK (length(media_type) BETWEEN 1 AND 100),
            source text NOT NULL CHECK (length(source) BETWEEN 1 AND 100),
            method text NOT NULL CHECK (method IN ('retrieved', 'uploaded')),
            pulled_at timestamptz NULL,
            period_start date NULL,
            period_end date NULL,
            client_entity_id uuid NULL,
            snapshot_id uuid NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            CONSTRAINT evidence_versions_number UNIQUE (tenant_id, evidence_item_id, version_no),
            CONSTRAINT evidence_versions_key_is_content_address CHECK (
                storage_key = 'tenants/' || tenant_id::text || '/sha256/' || fingerprint
            ),
            CONSTRAINT evidence_versions_retrieved_has_pull_time
                CHECK (method <> 'retrieved' OR pulled_at IS NOT NULL),
            CONSTRAINT evidence_versions_period
                CHECK (period_end IS NULL OR period_start IS NULL OR period_end >= period_start),
            FOREIGN KEY (tenant_id, engagement_id, evidence_item_id)
                REFERENCES evidence_items (tenant_id, engagement_id, id),
            FOREIGN KEY (tenant_id, client_entity_id) REFERENCES client_entities (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX evidence_versions_item ON evidence_versions "
        "(tenant_id, evidence_item_id, version_no DESC)"
    )
    op.execute(
        "CREATE INDEX evidence_items_engagement ON evidence_items (tenant_id, engagement_id)"
    )
    for table in ("evidence_items", "evidence_versions"):
        tenant_table(op, table)

    op.execute("REVOKE UPDATE, DELETE ON evidence_items FROM abacus_app")
    insert_columns(
        op,
        "evidence_items",
        ("id", "tenant_id", "engagement_id", "title", "created_by_kind", "created_by_id"),
    )
    insert_only(op, "evidence_versions")
    insert_columns(
        op,
        "evidence_versions",
        (
            "id",
            "tenant_id",
            "engagement_id",
            "evidence_item_id",
            "version_no",
            "fingerprint",
            "storage_key",
            "storage_version_id",
            "size_bytes",
            "media_type",
            "source",
            "method",
            "pulled_at",
            "period_start",
            "period_end",
            "client_entity_id",
            "snapshot_id",
        ),
    )

    # Second layer (ADR-004): no role, not even the owner, changes or removes a version.
    op.execute(
        """
        CREATE FUNCTION evidence_versions_immutable() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'evidence versions are immutable (ADR-004)'
                USING ERRCODE = 'insufficient_privilege';
        END
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER evidence_versions_no_update_or_delete "
        "BEFORE UPDATE OR DELETE ON evidence_versions "
        "FOR EACH ROW EXECUTE FUNCTION evidence_versions_immutable()"
    )
    op.execute(
        "CREATE TRIGGER evidence_versions_no_truncate BEFORE TRUNCATE ON evidence_versions "
        "FOR EACH STATEMENT EXECUTE FUNCTION evidence_versions_immutable()"
    )


def downgrade() -> None:
    op.execute("DROP TABLE evidence_versions")
    op.execute("DROP FUNCTION evidence_versions_immutable()")
    op.execute("DROP TABLE evidence_items")
