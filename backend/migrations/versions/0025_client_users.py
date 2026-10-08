"""Client users and invitations (SPEC-015; ADR-029, ADR-030).

Members are `staff` or `client`; a client membership never has a firm role, and client engagement
roles belong only to client memberships (a trigger). Invitations hold no token: only its
SHA-256, kept in `invitation_tokens` (not tenant-scoped, reached only through SECURITY DEFINER
functions) so an unauthenticated-to-the-firm acceptance can find its firm. Users and client
memberships are created only by reviewed definer functions; the application role never gets
INSERT on `users` or `memberships` (TASK-030 D3).

Revision ID: 0025
Revises: 0024
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None

_FUNCTIONS = (
    "invitation_token_set(uuid, text)",
    "invitation_token_find(text, text)",
    "provision_client_user(text, text, text, text)",
    "add_client_membership(uuid)",
    "remove_client_member(uuid, uuid)",
)


def upgrade() -> None:
    op.execute(
        "ALTER TABLE memberships ADD COLUMN kind text NOT NULL DEFAULT 'staff' "
        "CHECK (kind IN ('staff', 'client'))"
    )
    op.execute(
        "ALTER TABLE memberships ADD CONSTRAINT memberships_client_has_no_firm_role "
        "CHECK (kind = 'staff' OR firm_role IS NULL)"
    )
    op.execute("ALTER TABLE engagement_members DROP CONSTRAINT engagement_members_role_check")
    op.execute(
        "ALTER TABLE engagement_members ADD CONSTRAINT engagement_members_role_check "
        "CHECK (role IN ('engagement_partner', 'manager', 'senior', 'staff', 'reviewer', "
        "'client_admin', 'client_contributor'))"
    )
    op.execute(
        """
        CREATE FUNCTION engagement_members_kind() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        DECLARE member_kind text;
        BEGIN
            SELECT m.kind INTO member_kind FROM public.memberships m
             WHERE m.tenant_id = NEW.tenant_id AND m.user_id = NEW.user_id;
            IF (NEW.role IN ('client_admin', 'client_contributor'))
               IS DISTINCT FROM (member_kind = 'client') THEN
                RAISE EXCEPTION 'engagement role % does not match the membership kind', NEW.role
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER engagement_members_kind BEFORE INSERT OR UPDATE ON engagement_members "
        "FOR EACH ROW EXECUTE FUNCTION engagement_members_kind()"
    )
    op.execute(
        """
        CREATE TABLE client_invitations (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            email text NOT NULL CHECK (length(email) BETWEEN 3 AND 320),
            role text NOT NULL CHECK (role IN ('client_admin', 'client_contributor')),
            invited_by uuid NOT NULL,
            status text NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'accepted', 'revoked', 'expired')),
            expires_at timestamptz NOT NULL,
            accepted_by uuid,
            accepted_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id),
            FOREIGN KEY (tenant_id, invited_by) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX client_invitations_engagement ON client_invitations "
        "(tenant_id, engagement_id, created_at)"
    )
    op.execute(
        "CREATE UNIQUE INDEX client_invitations_one_pending ON client_invitations "
        "(tenant_id, engagement_id, lower(email)) WHERE status = 'pending'"
    )
    tenant_table(op, "client_invitations")
    op.execute("REVOKE UPDATE, DELETE ON client_invitations FROM abacus_app")
    insert_columns(
        op,
        "client_invitations",
        ("id", "tenant_id", "engagement_id", "email", "role", "invited_by", "expires_at"),
    )
    op.execute(
        "GRANT UPDATE (status, accepted_by, accepted_at, expires_at) "
        "ON client_invitations TO abacus_app"
    )
    # Not tenant-scoped: an acceptance doesn't know its firm until the token is found. The app role
    # has no privileges; only the definer functions below touch them.
    op.execute(
        """
        CREATE TABLE invitation_tokens (
            token_hash text PRIMARY KEY CHECK (token_hash ~ '^[0-9a-f]{64}$'),
            tenant_id uuid NOT NULL,
            invitation_id uuid NOT NULL UNIQUE,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE invitation_failures (
            identity_hash text NOT NULL CHECK (identity_hash ~ '^[0-9a-f]{64}$'),
            failed_at timestamptz NOT NULL DEFAULT clock_timestamp()
        )
        """
    )
    op.execute(
        "CREATE INDEX invitation_failures_identity ON invitation_failures "
        "(identity_hash, failed_at)"
    )
    op.execute("REVOKE ALL ON invitation_tokens, invitation_failures FROM abacus_app")
    # The firm's invitation gets (or, with NULL, loses) its token hash, in the session's tenant.
    op.execute(
        """
        CREATE FUNCTION invitation_token_set(p_invitation uuid, p_hash text) RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp
        SET statement_timeout = '5s'
        AS $$
        DECLARE v_tenant uuid := NULLIF(current_setting('app.tenant_id', true), '')::uuid;
        BEGIN
            IF v_tenant IS NULL OR NOT EXISTS (
                SELECT 1 FROM public.client_invitations
                 WHERE id = p_invitation AND tenant_id = v_tenant
            ) THEN
                RAISE EXCEPTION 'unknown invitation';
            END IF;
            DELETE FROM public.invitation_tokens WHERE invitation_id = p_invitation;
            IF p_hash IS NOT NULL THEN
                INSERT INTO public.invitation_tokens (token_hash, tenant_id, invitation_id)
                VALUES (p_hash, v_tenant, p_invitation);
            END IF;
        END $$
        """
    )
    # A token's firm and invitation, or nothing. Failures are recorded per identity; 10 in an hour
    # lock that identity for 15 minutes (SPEC-015 Q4). Same empty answer for every failure.
    op.execute(
        """
        CREATE FUNCTION invitation_token_find(p_hash text, p_identity text)
        RETURNS TABLE (tenant_id uuid, invitation_id uuid)
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp
        SET statement_timeout = '5s'
        AS $$
        BEGIN
            IF (SELECT count(*) FROM public.invitation_failures f
                 WHERE f.identity_hash = p_identity
                   AND f.failed_at > clock_timestamp() - interval '1 hour') >= 10
               AND (SELECT max(f.failed_at) FROM public.invitation_failures f
                     WHERE f.identity_hash = p_identity)
                   > clock_timestamp() - interval '15 minutes' THEN
                RETURN;
            END IF;
            RETURN QUERY SELECT t.tenant_id, t.invitation_id FROM public.invitation_tokens t
                          WHERE t.token_hash = p_hash;
            IF NOT FOUND THEN
                INSERT INTO public.invitation_failures (identity_hash) VALUES (p_identity);
                DELETE FROM public.invitation_failures
                 WHERE failed_at < clock_timestamp() - interval '1 day';
            END IF;
        END $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION provision_client_user(
            p_issuer text, p_subject text, p_email text, p_display_name text
        ) RETURNS uuid
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp
        SET statement_timeout = '5s'
        AS $$
        DECLARE v_id uuid;
        BEGIN
            INSERT INTO public.users (idp_issuer, idp_subject, email, display_name)
            VALUES (p_issuer, p_subject, p_email, p_display_name)
            ON CONFLICT (idp_issuer, idp_subject) DO NOTHING;
            SELECT id INTO v_id FROM public.users
             WHERE idp_issuer = p_issuer AND idp_subject = p_subject;
            RETURN v_id;
        END $$
        """
    )
    # A client membership in the session's firm: never a staff one, never a firm role.
    op.execute(
        """
        CREATE FUNCTION add_client_membership(p_user uuid) RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp
        SET statement_timeout = '5s'
        AS $$
        DECLARE v_tenant uuid := NULLIF(current_setting('app.tenant_id', true), '')::uuid;
                v_kind text;
        BEGIN
            IF v_tenant IS NULL THEN RAISE EXCEPTION 'no tenant'; END IF;
            SELECT kind INTO v_kind FROM public.memberships
             WHERE tenant_id = v_tenant AND user_id = p_user;
            IF v_kind = 'staff' THEN
                RAISE EXCEPTION 'already staff of this firm' USING ERRCODE = 'check_violation';
            ELSIF v_kind IS NULL THEN
                INSERT INTO public.memberships (tenant_id, user_id, kind)
                VALUES (v_tenant, p_user, 'client');
            ELSE
                UPDATE public.memberships SET status = 'active', revoked_at = NULL
                 WHERE tenant_id = v_tenant AND user_id = p_user AND status = 'revoked';
            END IF;
        END $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION remove_client_member(p_engagement uuid, p_user uuid) RETURNS boolean
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
    for function in _FUNCTIONS:
        op.execute(f"REVOKE ALL ON FUNCTION {function} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {function} TO abacus_app")


def downgrade() -> None:
    for function in _FUNCTIONS:
        op.execute(f"DROP FUNCTION {function}")
    op.execute("DROP TABLE invitation_failures")
    op.execute("DROP TABLE invitation_tokens")
    op.execute("DROP TABLE client_invitations")
    op.execute("DROP TRIGGER engagement_members_kind ON engagement_members")
    op.execute("DROP FUNCTION engagement_members_kind()")
    op.execute("ALTER TABLE engagement_members DROP CONSTRAINT engagement_members_role_check")
    op.execute(
        "ALTER TABLE engagement_members ADD CONSTRAINT engagement_members_role_check "
        "CHECK (role IN ('engagement_partner', 'manager', 'senior', 'staff', 'reviewer'))"
    )
    op.execute("ALTER TABLE memberships DROP CONSTRAINT memberships_client_has_no_firm_role")
    op.execute("ALTER TABLE memberships DROP COLUMN kind")
