"""Client access grants (F-03-T26; ADR-146, P-09; chapter 03 §4.2; DEC-34, DEC-129).

- `client_access_grants` (identity): 12 client roles across 9 scope kinds, optional
  `document_classes`, `expires_at` and `status` (pending, active, revoked, expired). The app may
  change only `status`; every change is also an insert-only `client_access_events` row.
- Every `engagement_members` row with `client_admin` or `client_contributor` becomes an `owner`
  or `contributor` grant at `engagement` scope (synthetic data only, P-38).
- Expand step (ADR-146: dual-read for one release): until the readers move to grants and the
  `engagement_members` CHECK narrows to staff roles, a trigger mirrors client rows into grants
  (insert or role change: an active grant; delete: the grant revoked). It runs as the caller,
  under the caller's tenant.

Revision ID: 0083
Revises: 0082
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0083"
down_revision = "0082"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE client_access_grants (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            user_id uuid NOT NULL REFERENCES users (id),
            contact_id uuid NULL,
            role text NOT NULL
                CHECK (role IN ('owner', 'contributor', 'plan_administrator', 'trustee',
                                'taxpayer', 'spouse', 'delegate', 'third_party', 'k1_recipient',
                                'tcwg', 'prospect', 'component_auditor')),
            scope_kind text NOT NULL
                CHECK (scope_kind IN ('client', 'client_entity', 'engagement', 'work_item',
                                      'request_item', 'k1_package', 'governance_room',
                                      'component', 'intake')),
            scope_id uuid NOT NULL,
            document_classes text[] NULL
                CHECK (document_classes IS NULL OR cardinality(document_classes) >= 1),
            granted_by uuid NULL,
            expires_at timestamptz NULL,
            status text NOT NULL DEFAULT 'active'
                CHECK (status IN ('pending', 'active', 'revoked', 'expired')),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, user_id, role, scope_kind, scope_id),
            FOREIGN KEY (tenant_id, user_id) REFERENCES memberships (tenant_id, user_id),
            FOREIGN KEY (tenant_id, contact_id) REFERENCES contacts (tenant_id, id)
        )
        """
    )
    tenant_table(op, "client_access_grants")
    op.execute("REVOKE DELETE ON client_access_grants FROM abacus_app")
    insert_columns(
        op,
        "client_access_grants",
        (
            *("tenant_id", "user_id", "contact_id", "role", "scope_kind", "scope_id"),
            *("document_classes", "granted_by", "expires_at", "status"),
        ),
    )
    op.execute("REVOKE UPDATE ON client_access_grants FROM abacus_app")
    op.execute("GRANT UPDATE (status) ON client_access_grants TO abacus_app")

    op.execute(
        """
        CREATE TABLE client_access_events (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            tenant_id uuid NOT NULL,
            grant_id uuid NOT NULL,
            event text NOT NULL CHECK (event IN ('granted', 'revoked', 'expired', 'activated')),
            by_user_id uuid NULL,
            at timestamptz NOT NULL DEFAULT clock_timestamp(),
            FOREIGN KEY (tenant_id, grant_id) REFERENCES client_access_grants (tenant_id, id)
        )
        """
    )
    tenant_table(op, "client_access_events")
    op.execute("REVOKE UPDATE, DELETE ON client_access_events FROM abacus_app")
    insert_columns(op, "client_access_events", ("tenant_id", "grant_id", "event", "by_user_id"))

    # Backfill (synthetic data only): the owner is held to row-level security too, so the
    # tables read and written are unforced for the statements, as 0068 does.
    tables = ("engagement_members", "client_access_grants", "client_access_events")
    for table in tables:
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        INSERT INTO client_access_grants (tenant_id, user_id, role, scope_kind, scope_id)
        SELECT m.tenant_id, m.user_id,
               CASE m.role WHEN 'client_admin' THEN 'owner' ELSE 'contributor' END,
               'engagement', m.engagement_id
          FROM engagement_members m
         WHERE m.role IN ('client_admin', 'client_contributor')
        """
    )
    op.execute(
        """
        INSERT INTO client_access_events (tenant_id, grant_id, event)
        SELECT tenant_id, id, 'granted' FROM client_access_grants
        """
    )
    for table in tables:
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")

    op.execute(
        """
        CREATE FUNCTION mirror_client_member_grant() RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = pg_catalog, public, pg_temp
        AS $$
        DECLARE
            v_grant uuid;
        BEGIN
            IF TG_OP IN ('UPDATE', 'DELETE')
               AND OLD.role IN ('client_admin', 'client_contributor') THEN
                UPDATE public.client_access_grants SET status = 'revoked'
                 WHERE tenant_id = OLD.tenant_id AND user_id = OLD.user_id
                   AND scope_kind = 'engagement' AND scope_id = OLD.engagement_id
                   AND role = CASE OLD.role WHEN 'client_admin' THEN 'owner'
                                            ELSE 'contributor' END
                   AND status = 'active'
                RETURNING id INTO v_grant;
                IF v_grant IS NOT NULL THEN
                    INSERT INTO public.client_access_events (tenant_id, grant_id, event)
                    VALUES (OLD.tenant_id, v_grant, 'revoked');
                END IF;
            END IF;
            IF TG_OP IN ('INSERT', 'UPDATE')
               AND NEW.role IN ('client_admin', 'client_contributor') THEN
                v_grant := NULL;
                INSERT INTO public.client_access_grants
                       (tenant_id, user_id, role, scope_kind, scope_id)
                VALUES (NEW.tenant_id, NEW.user_id,
                        CASE NEW.role WHEN 'client_admin' THEN 'owner' ELSE 'contributor' END,
                        'engagement', NEW.engagement_id)
                ON CONFLICT (tenant_id, user_id, role, scope_kind, scope_id) DO NOTHING
                RETURNING id INTO v_grant;
                IF v_grant IS NOT NULL THEN
                    INSERT INTO public.client_access_events (tenant_id, grant_id, event)
                    VALUES (NEW.tenant_id, v_grant, 'granted');
                ELSE
                    UPDATE public.client_access_grants SET status = 'active'
                     WHERE tenant_id = NEW.tenant_id AND user_id = NEW.user_id
                       AND scope_kind = 'engagement' AND scope_id = NEW.engagement_id
                       AND role = CASE NEW.role WHEN 'client_admin' THEN 'owner'
                                                ELSE 'contributor' END
                       AND status <> 'active'
                    RETURNING id INTO v_grant;
                    IF v_grant IS NOT NULL THEN
                        INSERT INTO public.client_access_events (tenant_id, grant_id, event)
                        VALUES (NEW.tenant_id, v_grant, 'activated');
                    END IF;
                END IF;
            END IF;
            RETURN NULL;
        END
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER engagement_members_mirror_grant "
        "AFTER INSERT OR UPDATE OF role OR DELETE ON engagement_members "
        "FOR EACH ROW EXECUTE FUNCTION mirror_client_member_grant()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER engagement_members_mirror_grant ON engagement_members")
    op.execute("DROP FUNCTION mirror_client_member_grant()")
    op.execute("DROP TABLE client_access_events")
    op.execute("DROP TABLE client_access_grants")
