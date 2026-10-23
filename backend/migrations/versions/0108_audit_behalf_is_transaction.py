"""Audit rows name only the person their transaction acts for (Q-02 AC-15; §5).

`audit_events.on_behalf_of_user_id` must equal the transaction setting `app.on_behalf_of`, which
the unit of work sets from the context. This binds the person in the same way 0003 binds the
actor, so an agent's or the platform's row can't name someone else. History is insert-only and
can't be back-filled, so the check is NOT VALID: it holds for every new row.

Revision ID: 0108
Revises: 0107
"""

from __future__ import annotations

from alembic import op

revision = "0108"
down_revision = "0107"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE audit_events ADD CONSTRAINT audit_events_behalf_is_transaction CHECK "
        "(on_behalf_of_user_id IS NOT DISTINCT FROM "
        "NULLIF(current_setting('app.on_behalf_of', true), '')::uuid) NOT VALID"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE audit_events DROP CONSTRAINT audit_events_behalf_is_transaction")
