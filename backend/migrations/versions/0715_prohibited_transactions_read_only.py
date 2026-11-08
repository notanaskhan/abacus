"""S30 end pass: `v_prohibited_transactions` is a read (A-05-T48; Q-03-T206 finding; DEC-2716).

0685 granted the app role SELECT on the view, but the role also held INSERT, UPDATE and DELETE on
it through the database's default privileges, so a write through the view reached
`ebp_late_remittances` (checked as the caller, `security_invoker`, so no wider than the table's
own grants, but a second write path the row never meant). The view is made read-only for the app.

Revision ID: 0715
Revises: 0714
"""

from __future__ import annotations

from alembic import op

revision = "0715"
down_revision = "0714"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON v_prohibited_transactions FROM abacus_app"
    )


def downgrade() -> None:
    # Expand-only: the write path is not restored.
    pass
