"""A connection's reauth notice is sent once per due date (A-02-T25; A-02 §3.11; DEC-708).

`connections.reauth_noticed_for` holds the `reauth_due_at` value the daily health pass last told
the connection's leads about, so a notice goes once per due date and again only when the due date
moves. Expand-only: a nullable column and its update grant.

Revision ID: 0271
Revises: 0270 (renumbered on rebase at the S13 batch merge)
"""

from __future__ import annotations

from alembic import op

revision = "0271"
down_revision = "0270"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE connections ADD COLUMN reauth_noticed_for timestamptz NULL")
    op.execute("GRANT UPDATE (reauth_noticed_for) ON connections TO abacus_app")


def downgrade() -> None:
    op.execute("REVOKE UPDATE (reauth_noticed_for) ON connections FROM abacus_app")
    op.execute("ALTER TABLE connections DROP COLUMN reauth_noticed_for")
