"""Ethical walls (SPEC-002; TASK-016 design §1; ADR-026).

A wall shuts one person out of one client: every engagement of that client, present and future,
whatever their role. Walls are never deleted: removing one marks it `removed` (forward-only),
so who was walled from what, and when, stays on record. At most one active wall per person and
client.

Revision ID: 0012
Revises: 0011
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE ethical_walls (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            user_id uuid NOT NULL,
            client_id uuid NOT NULL,
            status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'removed')),
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            removed_by uuid NULL,
            removed_at timestamptz NULL,
            UNIQUE (tenant_id, id),
            CONSTRAINT ethical_walls_removed
                CHECK ((status = 'removed') = (removed_at IS NOT NULL AND removed_by IS NOT NULL)),
            FOREIGN KEY (tenant_id, user_id) REFERENCES memberships (tenant_id, user_id),
            FOREIGN KEY (tenant_id, client_id) REFERENCES clients (tenant_id, id),
            FOREIGN KEY (tenant_id, created_by) REFERENCES memberships (tenant_id, user_id),
            FOREIGN KEY (tenant_id, removed_by) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX ethical_walls_one_active ON ethical_walls (tenant_id, user_id, "
        "client_id) WHERE status = 'active'"
    )
    op.execute("CREATE INDEX ethical_walls_user ON ethical_walls (tenant_id, user_id, status)")
    tenant_table(op, "ethical_walls")
    op.execute("REVOKE UPDATE, DELETE ON ethical_walls FROM abacus_app")
    insert_columns(op, "ethical_walls", ("id", "tenant_id", "user_id", "client_id", "created_by"))
    op.execute("GRANT UPDATE (status, removed_by, removed_at) ON ethical_walls TO abacus_app")
    op.execute(
        """
        CREATE FUNCTION ethical_walls_forward_only() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF OLD.status <> 'active' THEN
                RAISE EXCEPTION 'ethical wall % is removed', OLD.id
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF NEW.status <> 'removed' THEN
                RAISE EXCEPTION 'ethical wall % may only be removed', OLD.id
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF NEW.user_id IS DISTINCT FROM OLD.user_id
               OR NEW.client_id IS DISTINCT FROM OLD.client_id
               OR NEW.created_by IS DISTINCT FROM OLD.created_by
               OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
                RAISE EXCEPTION 'ethical wall % is immutable', OLD.id
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER ethical_walls_forward_only BEFORE UPDATE ON ethical_walls "
        "FOR EACH ROW EXECUTE FUNCTION ethical_walls_forward_only()"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE ethical_walls NO FORCE ROW LEVEL SECURITY")
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM ethical_walls) THEN "
        "RAISE EXCEPTION 'refusing to downgrade: ethical walls exist'; END IF; END $$"
    )
    op.execute("DROP TABLE ethical_walls")
    op.execute("DROP FUNCTION ethical_walls_forward_only()")
