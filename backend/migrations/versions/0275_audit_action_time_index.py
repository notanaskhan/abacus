"""The pilot metric reads' index (Q-04-T006; DEC-715): `audit_events (tenant_id, action,
occurred_at)`, which `audit_trail.metrics.event_counts` and `first_to_last_durations` read by.
Before Jun 1, 2027 the table is small enough to index in the migration's transaction (ADR-135).

Revision ID: 0275
Revises: 0274 (renumbered on rebase at the S13 batch merge)
"""

from __future__ import annotations

from alembic import op

revision = "0275"
down_revision = "0274"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS audit_events_action_time ON audit_events "
        "(tenant_id, action, occurred_at)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS audit_events_action_time")
