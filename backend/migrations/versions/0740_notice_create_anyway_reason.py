"""N-04-T07 (N-04 US-2.3; DEC-2953): "Create anyway" past a possible duplicate names its reason.

Expand-only: one nullable column on `notice_intakes`, a code like the discard reason's, and the app
role's UPDATE on it.

Revision ID: 0740
Revises: 0715
"""

from __future__ import annotations

from alembic import op

revision = "0740"
down_revision = "0715"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE notice_intakes ADD COLUMN create_anyway_reason_code text NULL "
        "CHECK (create_anyway_reason_code ~ '^[a-z][a-z0-9_]{0,59}$')"
    )
    op.execute("GRANT UPDATE (create_anyway_reason_code) ON notice_intakes TO abacus_app")


def downgrade() -> None:
    op.execute("REVOKE UPDATE (create_anyway_reason_code) ON notice_intakes FROM abacus_app")
    op.execute("ALTER TABLE notice_intakes DROP COLUMN create_anyway_reason_code")
