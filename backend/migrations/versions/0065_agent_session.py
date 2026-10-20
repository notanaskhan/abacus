"""The agent procedure session (SPEC-044; TASK-109).

- `procedure_session_events` (insert-only): a person approving the session's plan.
- `item_results.adopted_assessment_id`: the agent assessment a person adopted as this result.

Revision ID: 0065
Revises: 0064
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0065"
down_revision = "0064"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE procedure_session_events (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            procedure_id uuid NOT NULL,
            kind text NOT NULL CHECK (kind IN ('plan_approved')),
            by_user uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            FOREIGN KEY (tenant_id, procedure_id) REFERENCES procedures (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX procedure_session_events_by_procedure "
        "ON procedure_session_events (tenant_id, procedure_id)"
    )
    tenant_table(op, "procedure_session_events")
    op.execute("REVOKE UPDATE, DELETE ON procedure_session_events FROM abacus_app")
    insert_columns(
        op, "procedure_session_events", ("tenant_id", "procedure_id", "kind", "by_user")
    )
    op.execute("ALTER TABLE item_results ADD COLUMN adopted_assessment_id uuid NULL")
    op.execute("GRANT INSERT (adopted_assessment_id) ON item_results TO abacus_app")


def downgrade() -> None:
    op.execute("ALTER TABLE item_results DROP COLUMN adopted_assessment_id")
    op.execute("DROP TABLE procedure_session_events")
