"""The audit trail's read tables (G-02-T10; SPEC-349 §7; G-02 §4.2 `NNNN_audit_trail_read`).

- `audit_event_labels`: a rebuildable projection of `audit_events` for ADM-07's search, one row
  per event (`(tenant_id, seq)`): the actor's and the target's display labels, a `keywords`
  tsvector over labels and the action's words only, and the event's client, office and
  engagement. **No Restricted text by construction:** labels come only through the platform
  labelers, which refuse anything above `confidential`, and no value is ever indexed (DEC-60,
  security review M4). The app inserts and re-writes rows (the indexer is idempotent on
  `(tenant_id, seq)`); nothing deletes one. RLS forced; GIN on `keywords`.
- `audit_exports`: ADM-07's export jobs (G-02-T17 fills it): requested by a person only
  (`requested_by_kind = 'human'`), the filter, the status, the seq range, the bundle's keys and
  digest, the signing key reference and the expiry. RLS forced; never deleted by the app.

Both tables in one migration, as G-02 §4.2 plans; G-02-T17 adds none. Expand-only.

Revision ID: 0192
Revises: 0180
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0192"
down_revision = "0180"
branch_labels = None
depends_on = None

LABEL_COLUMNS = (
    "tenant_id",
    "seq",
    "effective_at",
    "actor_label",
    "target_label",
    "keywords",
    "client_id",
    "office_id",
    "engagement_id",
)
LABEL_UPDATES = (
    "effective_at",
    "actor_label",
    "target_label",
    "keywords",
    "client_id",
    "office_id",
    "engagement_id",
    "indexed_at",
)
EXPORT_COLUMNS = (
    "id",
    "tenant_id",
    "requested_by",
    "requested_by_kind",
    "filter",
    "from_date",
    "to_date",
    "include_values",
    "idempotency_key",
)
EXPORT_UPDATES = (
    "status",
    "seq_from",
    "seq_to",
    "row_count",
    "csv_key",
    "manifest_key",
    "manifest_sha256",
    "signature_key_ref",
    "expires_at",
    "updated_at",
)


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE audit_event_labels (
            tenant_id uuid NOT NULL,
            seq bigint NOT NULL,
            effective_at timestamptz NOT NULL,
            actor_label text NULL CHECK (length(actor_label) BETWEEN 1 AND 200),
            target_label text NULL CHECK (length(target_label) BETWEEN 1 AND 300),
            keywords tsvector NOT NULL,
            client_id uuid NULL,
            office_id uuid NULL,
            engagement_id uuid NULL,
            indexed_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (tenant_id, seq)
        )
        """
    )
    tenant_table(op, "audit_event_labels")
    op.execute("REVOKE DELETE, TRUNCATE ON audit_event_labels FROM abacus_app")
    insert_columns(op, "audit_event_labels", LABEL_COLUMNS)
    op.execute("REVOKE UPDATE ON audit_event_labels FROM abacus_app")
    op.execute(f"GRANT UPDATE ({', '.join(LABEL_UPDATES)}) ON audit_event_labels TO abacus_app")
    op.execute(
        "CREATE INDEX audit_event_labels_keywords ON audit_event_labels USING gin (keywords)"
    )
    op.execute(
        "CREATE INDEX audit_event_labels_newest ON audit_event_labels (tenant_id, seq DESC)"
    )

    op.execute(
        """
        CREATE TABLE audit_exports (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            requested_by uuid NOT NULL,
            requested_by_kind text NOT NULL CHECK (requested_by_kind = 'human'),
            filter jsonb NOT NULL DEFAULT '{}'::jsonb,
            from_date date NOT NULL,
            to_date date NOT NULL,
            include_values boolean NOT NULL DEFAULT false,
            idempotency_key text NULL CHECK (length(idempotency_key) BETWEEN 1 AND 255),
            status text NOT NULL DEFAULT 'requested'
                CHECK (status IN ('requested', 'building', 'ready', 'downloaded', 'expired',
                                  'failed')),
            seq_from bigint NULL,
            seq_to bigint NULL,
            row_count integer NULL CHECK (row_count >= 0),
            csv_key text NULL,
            manifest_key text NULL,
            manifest_sha256 text NULL CHECK (manifest_sha256 ~ '^[0-9a-f]{64}$'),
            signature_key_ref text NULL,
            expires_at timestamptz NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CHECK (to_date >= from_date AND to_date - from_date <= 92),
            UNIQUE (tenant_id, requested_by, idempotency_key)
        )
        """
    )
    tenant_table(op, "audit_exports")
    op.execute("REVOKE DELETE, TRUNCATE ON audit_exports FROM abacus_app")
    insert_columns(op, "audit_exports", EXPORT_COLUMNS)
    op.execute("REVOKE UPDATE ON audit_exports FROM abacus_app")
    op.execute(f"GRANT UPDATE ({', '.join(EXPORT_UPDATES)}) ON audit_exports TO abacus_app")
    op.execute(
        "CREATE INDEX audit_exports_requester ON audit_exports "
        "(tenant_id, requested_by, created_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE audit_exports")
    op.execute("DROP TABLE audit_event_labels")
