"""A-04-T19 (A-04 §4.2; DEC-2055): the fraud brainstorm session's row version. Expand only.

`fraud_brainstorm_sessions` (0613) gains `row_version` (default 1), so a stale edit of the session
or its minutes answers 409 `version_conflict` (AUD-05 b). The app may update it with the session's
other columns.

Revision ID: 0651
Revises: 0650
"""

from __future__ import annotations

from alembic import op

revision = "0651"
down_revision = "0650"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE fraud_brainstorm_sessions "
        "ADD COLUMN row_version integer NOT NULL DEFAULT 1 CHECK (row_version >= 1)"
    )
    op.execute("GRANT UPDATE (row_version) ON fraud_brainstorm_sessions TO abacus_app")


def downgrade() -> None:
    op.execute("REVOKE UPDATE (row_version) ON fraud_brainstorm_sessions FROM abacus_app")
    op.execute("ALTER TABLE fraud_brainstorm_sessions DROP COLUMN row_version")
