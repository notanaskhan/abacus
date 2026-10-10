"""Synthetic firms, for the model data boundary (SPEC-026 AC-3; TASK-049).

A real model may see a firm's data only when the firm is synthetic. The application role gets no
insert or update on the column: only the local seed and evaluation runs set it, as the owner.

Revision ID: 0038
Revises: 0037
"""

from __future__ import annotations

from alembic import op

revision = "0038"
down_revision = "0037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE firms ADD COLUMN synthetic boolean NOT NULL DEFAULT false")


def downgrade() -> None:
    op.execute("ALTER TABLE firms DROP COLUMN synthetic")
