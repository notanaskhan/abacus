"""G-01-T12: service-line need-to-know (G-01 §4.2, AC10.1 to AC10.4; DEC-380).

- `service_line_policies` (new, identity): one row per firm and service line (`audit`, `tax`,
  `cas`, `advisory`) saying who may read the line's content: `engagement_team_only` or
  `service_line` (read-only for the line's members, never Audit or an attest client: DEC-380),
  and how a cross-line request is handled (`handoffs_only`; `by_request` is stored and behaves as
  hand-offs only until a flow is designed, G-01 OQ-2). A firm without a row reads the line as
  enabled, `engagement_team_only`, `handoffs_only` (fail closed).
- Audit is locked: the CHECK `service_line <> 'audit' OR content_visible_to =
  'engagement_team_only'` holds whatever the app sends (422 `audit_locked` above it).
- The lead, when named, is a member of the firm. Rows are never deleted by the app; the editable
  columns are updated against `version`.
- A row is a live person's own (DEC-383): the trigger `service_line_policies_actor` refuses an
  insert or update whose `app.actor_kind` isn't `human` or whose `updated_by` isn't the
  transaction's `app.actor_id`.

Revision ID: 0167
Revises: 0165 (re-pointed at the S9 batch merge)
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0167"
down_revision = "0165"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE service_line_policies (
            tenant_id uuid NOT NULL,
            service_line text NOT NULL
                CHECK (service_line IN ('audit', 'tax', 'cas', 'advisory')),
            enabled boolean NOT NULL DEFAULT true,
            lead_user_id uuid NULL,
            content_visible_to text NOT NULL DEFAULT 'engagement_team_only'
                CHECK (content_visible_to IN ('engagement_team_only', 'service_line')),
            cross_line_access text NOT NULL DEFAULT 'handoffs_only'
                CHECK (cross_line_access IN ('handoffs_only', 'by_request')),
            version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
            updated_by uuid NOT NULL,
            updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            PRIMARY KEY (tenant_id, service_line),
            CONSTRAINT service_line_policies_audit_locked
                CHECK (service_line <> 'audit' OR content_visible_to = 'engagement_team_only'),
            FOREIGN KEY (tenant_id, lead_user_id) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    tenant_table(op, "service_line_policies")
    insert_columns(
        op,
        "service_line_policies",
        (
            "tenant_id",
            "service_line",
            "enabled",
            "lead_user_id",
            "content_visible_to",
            "cross_line_access",
            "updated_by",
        ),
    )
    op.execute("REVOKE UPDATE, DELETE ON service_line_policies FROM abacus_app")
    op.execute(
        "GRANT UPDATE (enabled, lead_user_id, content_visible_to, cross_line_access, version, "
        "updated_by, updated_at) ON service_line_policies TO abacus_app"
    )
    op.execute(
        """
        CREATE FUNCTION service_line_policies_actor() RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = pg_catalog, public, pg_temp
        AS $$
        BEGIN
            IF current_setting('app.actor_kind', true) IS DISTINCT FROM 'human'
               OR NEW.updated_by::text IS DISTINCT FROM current_setting('app.actor_id', true) THEN
                RAISE EXCEPTION 'a service-line policy is a live person''s own'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER service_line_policies_actor BEFORE INSERT OR UPDATE "
        "ON service_line_policies FOR EACH ROW EXECUTE FUNCTION service_line_policies_actor()"
    )


def downgrade() -> None:
    op.execute("DROP TABLE service_line_policies")
    op.execute("DROP FUNCTION service_line_policies_actor()")
