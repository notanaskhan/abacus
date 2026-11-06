"""A-05-T32 (DEC-2361): a participant's actual match for EBP-04 c, expand-only.

`ebp_participants.match_ytd` is what the census or the register's participant detail says the
employer matched for the year, so the Testing tab compares it to the plan's rule. Nullable with no
default, so no table rewrite; a census without it still imports.

Revision ID: 0673
Revises: 0672
"""

from __future__ import annotations

from alembic import op

revision = "0673"
down_revision = "0672"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE ebp_participants ADD COLUMN match_ytd numeric(20, 2) NULL "
        "CHECK (match_ytd >= 0)"
    )
    op.execute("GRANT INSERT (match_ytd) ON ebp_participants TO abacus_app")


def downgrade() -> None:
    op.execute("ALTER TABLE ebp_participants DROP COLUMN match_ytd")
