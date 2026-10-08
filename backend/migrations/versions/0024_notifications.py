"""In-app notifications (SPEC-013; ADR-024).

One row per recipient per catalogued event: identifiers and a kind, never text or client content.
Idempotent on (tenant, event, recipient), since the relay delivers at least once. Only `read_at`
changes. `notifications_purge` removes rows older than the retention period across firms (a
daily background task); it returns a count only.

Revision ID: 0024
Revises: 0023
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None

_PURGE = "notifications_purge(integer)"


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE notifications (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            recipient_user_id uuid NOT NULL,
            kind text NOT NULL CHECK (kind ~ '^[a-z][a-z_]*\\.[a-z][a-z_]*$'),
            event_id uuid NOT NULL,
            engagement_id uuid,
            subject_type text NOT NULL CHECK (subject_type ~ '^[a-z][a-z_]*$'),
            subject_id uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            read_at timestamptz,
            CONSTRAINT notifications_once UNIQUE (tenant_id, event_id, recipient_user_id),
            FOREIGN KEY (tenant_id, recipient_user_id) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX notifications_recipient ON notifications "
        "(tenant_id, recipient_user_id, created_at DESC)"
    )
    op.execute("CREATE INDEX notifications_created ON notifications (created_at)")
    tenant_table(op, "notifications")
    op.execute("REVOKE UPDATE, DELETE ON notifications FROM abacus_app")
    insert_columns(
        op,
        "notifications",
        (
            "id",
            "tenant_id",
            "recipient_user_id",
            "kind",
            "event_id",
            "engagement_id",
            "subject_type",
            "subject_id",
        ),
    )
    op.execute("GRANT UPDATE (read_at) ON notifications TO abacus_app")
    op.execute(
        """
        CREATE FUNCTION notifications_purge(p_days integer) RETURNS bigint
        LANGUAGE sql VOLATILE SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp
        SET statement_timeout = '60s'
        AS $$
            WITH gone AS (
                DELETE FROM public.notifications
                 WHERE created_at < clock_timestamp() - make_interval(days => greatest(p_days, 30))
                RETURNING 1
            )
            SELECT count(*) FROM gone
        $$
        """
    )
    op.execute(f"REVOKE ALL ON FUNCTION {_PURGE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {_PURGE} TO abacus_app")


def downgrade() -> None:
    op.execute(f"DROP FUNCTION {_PURGE}")
    op.execute("DROP TABLE notifications")
