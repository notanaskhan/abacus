"""An engagement's prior engagement, for roll-forward (SPEC-025 AC-2; TASK-048).

Set only when the engagement is created from a roll-forward proposal: the same firm (the composite
foreign key), never itself. Nullable: new clients and every existing engagement have none.

Revision ID: 0037
Revises: 0036
"""

from __future__ import annotations

from alembic import op

revision = "0037"
down_revision = "0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE engagements ADD COLUMN prior_engagement_id uuid NULL, "
        "ADD CONSTRAINT engagements_prior_fk FOREIGN KEY (tenant_id, prior_engagement_id) "
        "REFERENCES engagements (tenant_id, id), "
        "ADD CONSTRAINT engagements_prior_not_self CHECK (prior_engagement_id <> id)"
    )
    op.execute("GRANT INSERT (prior_engagement_id) ON engagements TO abacus_app")


def downgrade() -> None:
    op.execute("REVOKE INSERT (prior_engagement_id) ON engagements FROM abacus_app")
    op.execute("ALTER TABLE engagements DROP COLUMN prior_engagement_id")
