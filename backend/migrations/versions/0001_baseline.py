"""Baseline: verify what bootstrap.sql provides. Product tables start in TASK-007.

Revision ID: 0001
Revises:
"""

from __future__ import annotations

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Extensions need a database admin, so bootstrap.sql creates them; fail early if it hasn't run.
    op.execute(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT FROM pg_extension WHERE extname = 'vector') THEN "
        "RAISE EXCEPTION 'pgvector missing: run backend/migrations/bootstrap.sql first'; "
        "END IF; END $$"
    )
    # Default privileges would let the app role write Alembic's bookkeeping; it gets nothing.
    op.execute("REVOKE ALL ON alembic_version FROM abacus_app")


def downgrade() -> None:
    """Nothing to undo: the baseline creates no objects (alembic_version is Alembic's own)."""
