"""Ledger file imports (SPEC-028; TASK-052; ADR-107, ADR-110).

- The `import` provider: an uploaded export is a connector with reduced capabilities.
- `ledger_imports`: each uploaded export that scanned clean, stored write-once (content-addressed)
  and fingerprinted, with its check's outcome. Insert-only: an upload and its check are facts. One
  good import per entity and fingerprint, so the same file twice is recognised; a failed check
  doesn't count, so the same file can be uploaded again under the right format.
- Evidence provenance `imported`, which needs a pull time (when the import was read); the upload
  time is in the workbook's footer.

Revision ID: 0041
Revises: 0040
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0041"
down_revision = "0040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("connections", "connection_states"):
        op.execute(
            f"ALTER TABLE {table} DROP CONSTRAINT {table}_provider_check, "
            f"ADD CONSTRAINT {table}_provider_check CHECK (provider IN ('fake', 'import'))"
        )
    op.execute(
        "ALTER TABLE evidence_versions DROP CONSTRAINT evidence_versions_method_check, "
        "ADD CONSTRAINT evidence_versions_method_check "
        "CHECK (method IN ('retrieved', 'uploaded', 'imported')), "
        "ADD CONSTRAINT evidence_versions_imported_has_pull_time "
        "CHECK (method <> 'imported' OR pulled_at IS NOT NULL)"
    )
    op.execute(
        """
        CREATE TABLE ledger_imports (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            client_entity_id uuid NOT NULL,
            format text NOT NULL CHECK (format ~ '^[a-z][a-z0-9_]{0,40}$'),
            period_start date NOT NULL,
            period_end date NOT NULL CHECK (period_end >= period_start),
            storage_key text NOT NULL,
            storage_version_id text NOT NULL,
            fingerprint text NOT NULL CHECK (fingerprint ~ '^[0-9a-f]{64}$'),
            size_bytes integer NOT NULL CHECK (size_bytes > 0),
            scan_status text NOT NULL DEFAULT 'pending'
                CHECK (scan_status IN ('pending', 'clean', 'refused')),
            status text NOT NULL DEFAULT 'received'
                CHECK (status IN ('received', 'failed')),
            failure_code text NULL CHECK (failure_code ~ '^[a-z][a-z_]{0,49}$'),
            totals_from_lines boolean NOT NULL DEFAULT false,
            uploaded_by uuid NOT NULL,
            on_behalf boolean NOT NULL DEFAULT false,
            created_at timestamptz NOT NULL DEFAULT now(),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX ledger_imports_latest "
        "ON ledger_imports (tenant_id, client_entity_id, period_end, created_at)"
    )
    # The same file twice is one import (SPEC-028 AC-8); a failed check doesn't count, so the
    # same file can be uploaded again under the right format.
    op.execute(
        "CREATE UNIQUE INDEX ledger_imports_one_good_file "
        "ON ledger_imports (tenant_id, client_entity_id, fingerprint) WHERE status <> 'failed'"
    )
    tenant_table(op, "ledger_imports")
    op.execute("REVOKE UPDATE, DELETE ON ledger_imports FROM abacus_app")
    insert_columns(
        op,
        "ledger_imports",
        (
            "tenant_id",
            "engagement_id",
            "client_entity_id",
            "format",
            "period_start",
            "period_end",
            "storage_key",
            "storage_version_id",
            "fingerprint",
            "size_bytes",
            "scan_status",
            "status",
            "failure_code",
            "totals_from_lines",
            "uploaded_by",
            "on_behalf",
        ),
    )


def downgrade() -> None:
    op.execute("DROP TABLE ledger_imports")
    op.execute(
        "ALTER TABLE evidence_versions DROP CONSTRAINT evidence_versions_imported_has_pull_time, "
        "DROP CONSTRAINT evidence_versions_method_check, "
        "ADD CONSTRAINT evidence_versions_method_check "
        "CHECK (method IN ('retrieved', 'uploaded'))"
    )
    for table in ("connections", "connection_states"):
        op.execute(
            f"ALTER TABLE {table} DROP CONSTRAINT {table}_provider_check, "
            f"ADD CONSTRAINT {table}_provider_check CHECK (provider IN ('fake'))"
        )
