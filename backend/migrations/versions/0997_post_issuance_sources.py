"""Q-05-T17 (S52; TASK-8823; SPEC-711 AC-18; red): `post_issuance_sources`, a document filed from
INB-01 onto an archived engagement only as a post-issuance case's source (insert-only, forced
RLS). Nothing else on the locked work item changes. Expand-only.

Revision ID: 0997
Revises: 0996
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0997"
down_revision = "0996"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE post_issuance_sources (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            case_id uuid NOT NULL,
            evidence_version_id uuid NOT NULL,
            filed_from text NOT NULL CHECK (filed_from IN ('intake', 'upload')),
            created_by text NOT NULL CHECK (char_length(created_by) BETWEEN 1 AND 100),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, case_id, evidence_version_id),
            FOREIGN KEY (tenant_id, case_id) REFERENCES post_issuance_events (tenant_id, id)
        )
        """
    )
    tenant_table(op, "post_issuance_sources")
    insert_columns(
        op, "post_issuance_sources",
        ("tenant_id", "case_id", "evidence_version_id", "filed_from", "created_by"),
    )  # fmt: skip
    insert_only(op, "post_issuance_sources")


def downgrade() -> None:
    op.execute("DROP TABLE post_issuance_sources")
