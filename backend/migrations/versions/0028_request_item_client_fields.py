"""Request items' client facts (SPEC-020; TASK-035 D3, D4).

`client_visible` (default true) decides whether client users see an item at all;
`client_assignee_user_id` is the client contributor it's assigned to. The assignee must be a
member of the item's engagement (a composite key), and is cleared if they leave it. The service
checks they hold a client role.

Revision ID: 0028
Revises: 0027
"""

from __future__ import annotations

from alembic import op

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE request_items
            ADD COLUMN client_visible boolean NOT NULL DEFAULT true,
            ADD COLUMN client_assignee_user_id uuid NULL,
            ADD CONSTRAINT request_items_client_assignee
                FOREIGN KEY (tenant_id, engagement_id, client_assignee_user_id)
                REFERENCES engagement_members (tenant_id, engagement_id, user_id)
                ON DELETE SET NULL (client_assignee_user_id)
        """
    )
    op.execute(
        "CREATE INDEX request_items_client_assignee_idx ON request_items "
        "(tenant_id, client_assignee_user_id) WHERE client_assignee_user_id IS NOT NULL"
    )
    op.execute(
        "GRANT UPDATE (client_visible, client_assignee_user_id) ON request_items TO abacus_app"
    )


def downgrade() -> None:
    op.execute(
        "REVOKE UPDATE (client_visible, client_assignee_user_id) ON request_items FROM abacus_app"
    )
    op.execute("DROP INDEX request_items_client_assignee_idx")
    op.execute(
        "ALTER TABLE request_items DROP CONSTRAINT request_items_client_assignee, "
        "DROP COLUMN client_assignee_user_id, DROP COLUMN client_visible"
    )
