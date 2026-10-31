"""The sealed render snapshot (P-11-T11; P-11 §4.2, §4.6; C11 v1 §2; DEC-1561). Expand-only.

`generated_document_snapshots` (insert-only, `reporting_rows_immutable`): one row per generated
document version, holding the canonical JSON the version's `snapshot_sha256` was computed over
(layout, template version, the declared variables formatted by code, clause states and section
overrides). P-11-T08 sealed the hash only; the render job needs the values themselves, since a
kind's provider may answer only inside the consumer's call (DEC-1458), and the routes read them
back for "changes since snapshot" and the compare. The row is written in the consumer's unit of
work with the version, so a version without its snapshot never commits.

Classification (ADR-031): `snapshot` Confidential (client names, fees, dates; variable types are
money, date, text, percent, count, name and address, never a TIN); hashes and ids Internal. No
data is inserted.

Revision ID: 0522
Revises: 0565
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0522"
down_revision = "0565"
branch_labels = None
depends_on = None

TABLE = "generated_document_snapshots"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE {TABLE} (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            version_id uuid NOT NULL,
            snapshot jsonb NOT NULL CHECK (jsonb_typeof(snapshot) = 'object'),
            snapshot_sha256 text NOT NULL CHECK (snapshot_sha256 ~ '^[0-9a-f]{{64}}$'),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, version_id),
            FOREIGN KEY (tenant_id, version_id)
                REFERENCES generated_document_versions (tenant_id, id)
        )
        """
    )
    tenant_table(op, TABLE)
    insert_columns(op, TABLE, ("id", "tenant_id", "version_id", "snapshot", "snapshot_sha256"))
    insert_only(op, TABLE)
    op.execute(
        f"CREATE TRIGGER {TABLE}_immutable BEFORE UPDATE OR DELETE ON {TABLE} "
        "FOR EACH ROW EXECUTE FUNCTION reporting_rows_immutable()"
    )
    op.execute(
        f"CREATE TRIGGER {TABLE}_no_truncate BEFORE TRUNCATE ON {TABLE} "
        "FOR EACH STATEMENT EXECUTE FUNCTION reporting_rows_immutable()"
    )


def downgrade() -> None:
    op.execute(f"DROP TABLE {TABLE}")
