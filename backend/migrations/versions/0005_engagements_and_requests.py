"""Clients, client entities, engagements, request lists and request items (TASK-008 design §1).

Every foreign key carries `tenant_id`, so no row can point into another firm, and composite keys
keep related rows consistent: an engagement's entity belongs to its client; a request item's list
belongs to its engagement; creators and members are members of the same firm. Nothing is deleted
by the application; only engagements and request items change state (later tasks).

Revision ID: 0005
Revises: 0004
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import tenant_table

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE clients (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES firms (tenant_id),
            name text NOT NULL CHECK (length(name) BETWEEN 1 AND 200),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE client_entities (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            client_id uuid NOT NULL,
            name text NOT NULL CHECK (length(name) BETWEEN 1 AND 200),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, client_id, id),
            FOREIGN KEY (tenant_id, client_id) REFERENCES clients (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE engagements (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            client_id uuid NOT NULL,
            client_entity_id uuid NOT NULL,
            name text NOT NULL CHECK (length(name) BETWEEN 1 AND 200),
            type text NOT NULL DEFAULT 'audit' CHECK (type IN ('audit')),
            fiscal_period_start date NOT NULL,
            fiscal_period_end date NOT NULL,
            status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived')),
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            CONSTRAINT engagements_fiscal_period CHECK (fiscal_period_end > fiscal_period_start),
            FOREIGN KEY (tenant_id, client_id, client_entity_id)
                REFERENCES client_entities (tenant_id, client_id, id),
            FOREIGN KEY (tenant_id, created_by) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    op.execute(
        "ALTER TABLE engagement_members ADD CONSTRAINT engagement_members_engagement_fkey "
        "FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id)"
    )
    op.execute(
        """
        CREATE TABLE request_lists (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            -- One request list per engagement.
            UNIQUE (tenant_id, engagement_id),
            UNIQUE (tenant_id, engagement_id, id),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE request_items (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            request_list_id uuid NOT NULL,
            description text NOT NULL CHECK (length(description) BETWEEN 1 AND 2000),
            audit_area text NOT NULL CHECK (length(audit_area) BETWEEN 1 AND 100),
            status text NOT NULL DEFAULT 'open'
                CHECK (status IN ('open', 'received', 'ready_for_review', 'needs_revision')),
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, engagement_id, request_list_id)
                REFERENCES request_lists (tenant_id, engagement_id, id),
            FOREIGN KEY (tenant_id, created_by) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    op.execute("CREATE INDEX request_items_engagement ON request_items (tenant_id, engagement_id)")
    op.execute("CREATE INDEX engagements_tenant ON engagements (tenant_id, created_at)")

    for table in ("clients", "client_entities", "engagements", "request_lists", "request_items"):
        tenant_table(op, table)
    op.execute(
        "REVOKE DELETE ON clients, client_entities, engagements, request_lists, request_items "
        "FROM abacus_app"
    )
    # State changes come later (archive, request item status); the rest is never updated.
    op.execute("REVOKE UPDATE ON clients, client_entities, request_lists FROM abacus_app")
    # The creator becomes an engagement member (AC-4).
    op.execute("GRANT INSERT ON engagement_members TO abacus_app")


def downgrade() -> None:
    op.execute("REVOKE INSERT ON engagement_members FROM abacus_app")
    op.execute("DROP TABLE request_items")
    op.execute("DROP TABLE request_lists")
    op.execute("ALTER TABLE engagement_members DROP CONSTRAINT engagement_members_engagement_fkey")
    op.execute("DROP TABLE engagements")
    op.execute("DROP TABLE client_entities")
    op.execute("DROP TABLE clients")
