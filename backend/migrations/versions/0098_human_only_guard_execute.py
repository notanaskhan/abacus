"""Fix-up for 0097 (Q-02-T17): the app role may execute `abacus_human_only_actions()`.

The `audit_events_human_only` trigger runs as the inserting role, and functions here don't grant
EXECUTE to PUBLIC. Without this grant, every audit insert through the unit of work failed with
"permission denied for function abacus_human_only_actions". 0097's own test inserted as the
superuser and missed it. A test now inserts through the unit of work as the app role.

Revision ID: 0098
Revises: 0097
"""

from __future__ import annotations

from alembic import op

revision = "0098"
down_revision = "0097"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("GRANT EXECUTE ON FUNCTION abacus_human_only_actions() TO abacus_app")


def downgrade() -> None:
    op.execute("REVOKE EXECUTE ON FUNCTION abacus_human_only_actions() FROM abacus_app")
