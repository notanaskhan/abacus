"""Client access grants, contract step (F-03-T26; ADR-146; DEC-129; TASK-373).

The readers moved to `client_access_grants` with this revision, so:
- every client `engagement_members` row is made sure of as its grant, then deleted;
- `engagement_members.role` narrows to staff roles, and the 0083 mirror is dropped;
- `remove_client_member` revokes the engagement's owner and contributor grants (with their
  `client_access_events` rows) instead of deleting team rows;
- a grant's holder must have a client membership, as a client role always had (0025);
- `request_items.client_assignee_user_id` referenced the team table (0028). Its foreign key
  becomes two triggers with the same meaning: the assignee holds an active owner or
  contributor grant on the item's engagement, and revoking the last one clears the assignment
  (the key's `ON DELETE SET NULL`).

Downgrade puts the active owner and contributor engagement grants back as rows.

Revision ID: 0084
Revises: 0083
"""

from __future__ import annotations

from alembic import op

revision = "0084"
down_revision = "0083"
branch_labels = None
depends_on = None

_STAFF_ROLES = (
    "('engagement_partner', 'manager', 'senior', 'staff', 'reviewer', "
    "'eqr_reviewer', 'specialist', 'client_service')"
)
_ALL_ROLES = (
    "('engagement_partner', 'manager', 'senior', 'staff', 'reviewer', "
    "'eqr_reviewer', 'specialist', 'client_service', 'client_admin', 'client_contributor')"
)
_TABLES = (
    "engagement_members",
    "client_access_grants",
    "client_access_events",
    "memberships",
    "request_items",
)


def _unforced(statements: tuple[str, ...]) -> None:
    """Data statements (synthetic data only): the owner is held to row-level security too."""
    for table in _TABLES:
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
    for statement in statements:
        op.execute(statement)
    for table in _TABLES:
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")


def upgrade() -> None:
    op.execute("ALTER TABLE request_items DROP CONSTRAINT request_items_client_assignee")
    op.execute("DROP TRIGGER engagement_members_mirror_grant ON engagement_members")
    op.execute("DROP FUNCTION mirror_client_member_grant()")
    _unforced(
        (
            """
            INSERT INTO client_access_grants (tenant_id, user_id, role, scope_kind, scope_id)
            SELECT m.tenant_id, m.user_id,
                   CASE m.role WHEN 'client_admin' THEN 'owner' ELSE 'contributor' END,
                   'engagement', m.engagement_id
              FROM engagement_members m
             WHERE m.role IN ('client_admin', 'client_contributor')
            ON CONFLICT (tenant_id, user_id, role, scope_kind, scope_id)
            DO UPDATE SET status = 'active'
            """,
            "DELETE FROM engagement_members WHERE role IN ('client_admin', 'client_contributor')",
        )
    )
    op.execute("ALTER TABLE engagement_members DROP CONSTRAINT engagement_members_role_check")
    op.execute(
        "ALTER TABLE engagement_members ADD CONSTRAINT engagement_members_role_check "
        f"CHECK (role IN {_STAFF_ROLES})"
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION remove_client_member(p_engagement uuid, p_user uuid)
        RETURNS boolean
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp
        SET statement_timeout = '5s'
        AS $$
        DECLARE v_tenant uuid := NULLIF(current_setting('app.tenant_id', true), '')::uuid;
                v_grant uuid;
                v_found boolean := false;
        BEGIN
            FOR v_grant IN
                UPDATE public.client_access_grants SET status = 'revoked'
                 WHERE tenant_id = v_tenant AND user_id = p_user
                   AND scope_kind = 'engagement' AND scope_id = p_engagement
                   AND role IN ('owner', 'contributor') AND status = 'active'
                RETURNING id
            LOOP
                INSERT INTO public.client_access_events (tenant_id, grant_id, event)
                VALUES (v_tenant, v_grant, 'revoked');
                v_found := true;
            END LOOP;
            RETURN v_found;
        END $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION client_access_grants_kind() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM public.memberships m
                            WHERE m.tenant_id = NEW.tenant_id AND m.user_id = NEW.user_id
                              AND m.kind = 'client') THEN
                RAISE EXCEPTION 'a client access grant needs a client membership'
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER client_access_grants_kind BEFORE INSERT ON client_access_grants "
        "FOR EACH ROW EXECUTE FUNCTION client_access_grants_kind()"
    )
    op.execute(
        """
        CREATE FUNCTION request_items_client_assignee() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            IF NEW.client_assignee_user_id IS NOT NULL AND NOT EXISTS (
                SELECT 1 FROM public.client_access_grants g
                 WHERE g.tenant_id = NEW.tenant_id AND g.user_id = NEW.client_assignee_user_id
                   AND g.scope_kind = 'engagement' AND g.scope_id = NEW.engagement_id
                   AND g.role IN ('owner', 'contributor') AND g.status = 'active') THEN
                RAISE EXCEPTION 'the client assignee holds no grant on the engagement'
                    USING ERRCODE = 'foreign_key_violation',
                          CONSTRAINT = 'request_items_client_assignee';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER request_items_client_assignee "
        "BEFORE INSERT OR UPDATE OF client_assignee_user_id, engagement_id ON request_items "
        "FOR EACH ROW EXECUTE FUNCTION request_items_client_assignee()"
    )
    op.execute(
        """
        CREATE FUNCTION client_access_grants_unassign() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            IF OLD.status = 'active' AND NEW.status <> 'active'
               AND NEW.scope_kind = 'engagement' AND NEW.role IN ('owner', 'contributor')
               AND NOT EXISTS (
                   SELECT 1 FROM public.client_access_grants g
                    WHERE g.tenant_id = NEW.tenant_id AND g.user_id = NEW.user_id
                      AND g.scope_kind = 'engagement' AND g.scope_id = NEW.scope_id
                      AND g.role IN ('owner', 'contributor') AND g.status = 'active'
                      AND g.id <> NEW.id) THEN
                UPDATE public.request_items SET client_assignee_user_id = NULL
                 WHERE tenant_id = NEW.tenant_id AND engagement_id = NEW.scope_id
                   AND client_assignee_user_id = NEW.user_id;
            END IF;
            RETURN NULL;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER client_access_grants_unassign AFTER UPDATE OF status "
        "ON client_access_grants FOR EACH ROW EXECUTE FUNCTION client_access_grants_unassign()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER client_access_grants_unassign ON client_access_grants")
    op.execute("DROP FUNCTION client_access_grants_unassign()")
    op.execute("DROP TRIGGER request_items_client_assignee ON request_items")
    op.execute("DROP FUNCTION request_items_client_assignee()")
    op.execute("DROP TRIGGER client_access_grants_kind ON client_access_grants")
    op.execute("DROP FUNCTION client_access_grants_kind()")
    op.execute("ALTER TABLE engagement_members DROP CONSTRAINT engagement_members_role_check")
    op.execute(
        "ALTER TABLE engagement_members ADD CONSTRAINT engagement_members_role_check "
        f"CHECK (role IN {_ALL_ROLES})"
    )
    _unforced(
        (
            """
            INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role)
            SELECT DISTINCT ON (g.tenant_id, g.scope_id, g.user_id)
                   g.tenant_id, g.scope_id, g.user_id,
                   CASE g.role WHEN 'owner' THEN 'client_admin' ELSE 'client_contributor' END
              FROM client_access_grants g
             WHERE g.scope_kind = 'engagement' AND g.role IN ('owner', 'contributor')
               AND g.status = 'active'
             ORDER BY g.tenant_id, g.scope_id, g.user_id, g.role DESC
            ON CONFLICT DO NOTHING
            """,
            # An assignee without a row again (a revoked grant) can't satisfy 0028's key.
            """
            UPDATE request_items r SET client_assignee_user_id = NULL
             WHERE r.client_assignee_user_id IS NOT NULL AND NOT EXISTS (
                   SELECT 1 FROM engagement_members m
                    WHERE m.tenant_id = r.tenant_id AND m.engagement_id = r.engagement_id
                      AND m.user_id = r.client_assignee_user_id)
            """,
        )
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION remove_client_member(p_engagement uuid, p_user uuid)
        RETURNS boolean
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp
        SET statement_timeout = '5s'
        AS $$
        DECLARE v_tenant uuid := NULLIF(current_setting('app.tenant_id', true), '')::uuid;
        BEGIN
            DELETE FROM public.engagement_members
             WHERE tenant_id = v_tenant AND engagement_id = p_engagement AND user_id = p_user
               AND role IN ('client_admin', 'client_contributor');
            RETURN FOUND;
        END $$
        """
    )
    # 0083's mirror, as 0083 made it.
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
    op.execute(
        """
        ALTER TABLE request_items ADD CONSTRAINT request_items_client_assignee
            FOREIGN KEY (tenant_id, engagement_id, client_assignee_user_id)
            REFERENCES engagement_members (tenant_id, engagement_id, user_id)
            ON DELETE SET NULL (client_assignee_user_id)
        """
    )
