"""Findings and misstatements (SPEC-043; TASK-107).

- `findings` (insert-only): a finding on the engagement, from a fieldwork row or by hand.
- `misstatements` (insert-only): a misstatement recorded on a finding; the newest counts.

Revision ID: 0064
Revises: 0063
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0064"
down_revision = "0063"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE findings (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            procedure_id uuid NULL,
            selected_item_id uuid NULL,
            title text NOT NULL CHECK (length(title) BETWEEN 1 AND 200),
            description text NULL CHECK (length(description) BETWEEN 1 AND 2000),
            raised_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id),
            FOREIGN KEY (tenant_id, procedure_id) REFERENCES procedures (tenant_id, id),
            FOREIGN KEY (tenant_id, selected_item_id) REFERENCES selected_items (tenant_id, id)
        )
        """
    )
    op.execute("CREATE INDEX findings_by_engagement ON findings (tenant_id, engagement_id)")
    tenant_table(op, "findings")
    op.execute("REVOKE UPDATE, DELETE ON findings FROM abacus_app")
    insert_columns(
        op,
        "findings",
        (
            "tenant_id",
            "engagement_id",
            "procedure_id",
            "selected_item_id",
            "title",
            "description",
            "raised_by",
        ),
    )
    op.execute(
        """
        CREATE TABLE misstatements (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            finding_id uuid NOT NULL,
            kind text NOT NULL CHECK (kind IN ('factual', 'judgmental', 'projected')),
            amount numeric(18, 2) NOT NULL CHECK (amount <> 0),
            account_code text NULL CHECK (length(account_code) BETWEEN 1 AND 64),
            corrected boolean NOT NULL DEFAULT false,
            recorded_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            FOREIGN KEY (tenant_id, finding_id) REFERENCES findings (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX misstatements_by_finding "
        "ON misstatements (tenant_id, finding_id, created_at DESC)"
    )
    tenant_table(op, "misstatements")
    op.execute("REVOKE UPDATE, DELETE ON misstatements FROM abacus_app")
    insert_columns(
        op,
        "misstatements",
        ("tenant_id", "finding_id", "kind", "amount", "account_code", "corrected", "recorded_by"),
    )


def downgrade() -> None:
    op.execute("DROP TABLE misstatements")
    op.execute("DROP TABLE findings")
