"""The app inserts an issue with its own id (P-04-T30; DEC-714).

An issue's title, internal note and client wording are sealed bound to the issue's id
(`review.sealing`), so the id must exist before the row is written: the service mints it and the
app role may now insert `issues.id`. Nothing else changes.

Revision ID: 0274
Revises: 0273 (renumbered on rebase at the S13 batch merge)
"""

from __future__ import annotations

from alembic import op

revision = "0274"
down_revision = "0273"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("GRANT INSERT (id) ON issues TO abacus_app")


def downgrade() -> None:
    op.execute("REVOKE INSERT (id) ON issues FROM abacus_app")
