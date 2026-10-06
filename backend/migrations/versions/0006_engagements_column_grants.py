"""Column-level grants for the TASK-008 tables (both stage 4 reviews).

The app may insert only the columns it owns (never ids it didn't make up, timestamps or defaults it
shouldn't set) and may update only `status` on engagements and request items; everything else is
immutable to it. Engagement members: only the four identifying columns.

Revision ID: 0006
Revises: 0005
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

INSERT_COLUMNS: dict[str, tuple[str, ...]] = {
    "clients": ("id", "tenant_id", "name"),
    "client_entities": ("id", "tenant_id", "client_id", "name"),
    "engagements": (
        "id",
        "tenant_id",
        "client_id",
        "client_entity_id",
        "name",
        "fiscal_period_start",
        "fiscal_period_end",
        "created_by",
    ),
    "request_lists": ("id", "tenant_id", "engagement_id"),
    "request_items": (
        "id",
        "tenant_id",
        "engagement_id",
        "request_list_id",
        "description",
        "audit_area",
        "created_by",
    ),
    "engagement_members": ("tenant_id", "engagement_id", "user_id", "role"),
}


def upgrade() -> None:
    for table, columns in INSERT_COLUMNS.items():
        insert_columns(op, table, columns)
    op.execute("REVOKE UPDATE ON engagements, request_items FROM abacus_app")
    op.execute("GRANT UPDATE (status) ON engagements, request_items TO abacus_app")


def downgrade() -> None:
    op.execute("REVOKE UPDATE (status) ON engagements, request_items FROM abacus_app")
    op.execute("GRANT UPDATE ON engagements, request_items TO abacus_app")
    tables = "clients, client_entities, engagements, request_lists, request_items"
    op.execute("REVOKE INSERT ON " + tables + ", engagement_members FROM abacus_app")
    op.execute("GRANT INSERT ON " + tables + ", engagement_members TO abacus_app")
