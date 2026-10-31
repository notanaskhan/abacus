"""K-1 electronic-furnishing disclosures (S20e; T-02 §3.7, DV-12; Rev. Proc. 2012-17; DEC-1579).
Expand-only.

`k1_furnishing_disclosures` (insert-only): the firm's counsel-approved text a K-1 recipient reads
before consenting to electronic furnishing, one row per version, imported by a firm admin (content
belongs in the database, AGENTS 16; never seeded for a real firm). A recipient's consent names the
version they read (`k1_package_events.facts.disclosure_version_id`). Tax's table, forced RLS.

Classification (ADR-031): ids Internal; `body` Internal (the firm's own text).

Revision ID: 0590
Revises: 0580
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0590"
down_revision = "0580"
branch_labels = None
depends_on = None

INSERT = ("id", "tenant_id", "version_no", "body", "body_sha256", "imported_by")


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE k1_furnishing_disclosures (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            version_no integer NOT NULL CHECK (version_no >= 1),
            body text NOT NULL CHECK (char_length(btrim(body)) BETWEEN 1 AND 20000),
            body_sha256 text NOT NULL CHECK (body_sha256 ~ '^[0-9a-f]{64}$'),
            imported_by uuid NOT NULL,
            imported_at timestamptz NOT NULL DEFAULT abacus_now(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, version_no),
            FOREIGN KEY (tenant_id, imported_by) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    tenant_table(op, "k1_furnishing_disclosures")
    op.execute("REVOKE TRUNCATE ON k1_furnishing_disclosures FROM abacus_app")
    insert_only(op, "k1_furnishing_disclosures")
    insert_columns(op, "k1_furnishing_disclosures", INSERT)


def downgrade() -> None:
    op.execute("DROP TABLE k1_furnishing_disclosures")
