"""Break-glass support sessions (SPEC-012; ADR-028).

Staff have no standing access: a session for one firm, approved by a firm admin (or, in an
emergency, by a second staff member), time-boxed and read-only, with every request audited in
the firm's trail under the actor kind `support`. The quarterly access review reads every firm's
sessions only through `support_sessions_review`, which the owner role alone may execute (never the
application role, TASK-027 D4).

Revision ID: 0023
Revises: 0022
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None

_REVIEW = "support_sessions_review(timestamptz, timestamptz)"


def upgrade() -> None:
    op.execute("ALTER TABLE audit_events DROP CONSTRAINT audit_events_actor_kind_check")
    op.execute(
        "ALTER TABLE audit_events ADD CONSTRAINT audit_events_actor_kind_check "
        "CHECK (actor_kind IN ('human', 'agent', 'system', 'support'))"
    )
    op.execute(
        """
        CREATE TABLE support_sessions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            staff_id uuid NOT NULL,
            staff_subject text NOT NULL CHECK (length(staff_subject) BETWEEN 1 AND 255),
            reason text NOT NULL CHECK (length(reason) BETWEEN 20 AND 1000),
            scope text NOT NULL CHECK (scope IN ('metadata', 'content')),
            duration_minutes integer NOT NULL CHECK (duration_minutes BETWEEN 1 AND 240),
            emergency boolean NOT NULL,
            status text NOT NULL DEFAULT 'requested'
                CHECK (status IN ('requested', 'active', 'ended', 'revoked', 'expired')),
            approved_by_kind text CHECK (approved_by_kind IN ('firm_admin', 'staff')),
            approved_by uuid,
            starts_at timestamptz,
            expires_at timestamptz,
            ended_at timestamptz,
            acknowledged_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            CONSTRAINT support_sessions_emergency_hour
                CHECK (NOT emergency OR duration_minutes <= 60),
            CONSTRAINT support_sessions_approved CHECK (
                (status = 'requested') = (approved_by IS NULL AND starts_at IS NULL)
                OR status = 'revoked'
            ),
            CONSTRAINT support_sessions_not_self_approved CHECK (approved_by <> staff_id)
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX support_sessions_one_active ON support_sessions "
        "(tenant_id, staff_id) WHERE status IN ('requested', 'active')"
    )
    op.execute("CREATE INDEX support_sessions_created ON support_sessions (created_at)")
    tenant_table(op, "support_sessions")
    op.execute("REVOKE UPDATE, DELETE ON support_sessions FROM abacus_app")
    insert_columns(
        op,
        "support_sessions",
        (
            "id",
            "tenant_id",
            "staff_id",
            "staff_subject",
            "reason",
            "scope",
            "duration_minutes",
            "emergency",
        ),
    )
    op.execute(
        "GRANT UPDATE (status, approved_by_kind, approved_by, starts_at, expires_at, ended_at, "
        "acknowledged_at) ON support_sessions TO abacus_app"
    )
    op.execute(
        """
        CREATE FUNCTION support_sessions_review(p_from timestamptz, p_to timestamptz)
        RETURNS TABLE (
            id uuid, tenant_id uuid, staff_id uuid, staff_subject text, reason_sha256 text,
            scope text, emergency boolean, status text, approved_by_kind text,
            starts_at timestamptz, expires_at timestamptz, ended_at timestamptz,
            created_at timestamptz, requests bigint
        )
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp
        SET statement_timeout = '30s'
        AS $$
            SELECT s.id, s.tenant_id, s.staff_id, s.staff_subject,
                   encode(sha256(convert_to(s.reason, 'UTF8')), 'hex'), s.scope, s.emergency,
                   s.status, s.approved_by_kind, s.starts_at, s.expires_at, s.ended_at,
                   s.created_at,
                   (SELECT count(*) FROM public.audit_events a
                     WHERE a.tenant_id = s.tenant_id AND a.action = 'support.request'
                       AND a.target_type = 'support_session' AND a.target_id = s.id::text)
              FROM public.support_sessions s
             WHERE s.created_at >= p_from AND s.created_at < p_to
             ORDER BY s.created_at, s.id
        $$
        """
    )
    op.execute(f"REVOKE ALL ON FUNCTION {_REVIEW} FROM PUBLIC")


def downgrade() -> None:
    op.execute(f"DROP FUNCTION {_REVIEW}")
    op.execute("DROP TABLE support_sessions")
    op.execute("ALTER TABLE audit_events DROP CONSTRAINT audit_events_actor_kind_check")
    op.execute(
        "ALTER TABLE audit_events ADD CONSTRAINT audit_events_actor_kind_check "
        "CHECK (actor_kind IN ('human', 'agent', 'system'))"
    )
