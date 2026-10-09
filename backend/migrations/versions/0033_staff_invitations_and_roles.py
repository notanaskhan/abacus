"""Staff invitations, firm roles and revocation (SPEC-024 AC-3, AC-4; TASK-041).

- `staff_invitations` (tenant-scoped) and `staff_invitation_tokens` (global, definer functions
  only), parallel to the client ones (D1), sharing the client lockout (`invitation_failures`).
- `add_staff_membership`: a staff membership with a firm role in the session's firm; never for
  a client contact of that firm; a revoked one is reactivated with the new role.
- `membership_set_firm_role`, `membership_revoke`: in the session's firm, staff only, never
  leaving it without an active firm administrator (D2). Answer `ok`, `not_found` or
  `last_admin`.

Revision ID: 0033
Revises: 0032
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None

_FUNCTIONS = (
    "staff_invitation_token_set(uuid, text)",
    "staff_invitation_token_find(text, text)",
    "add_staff_membership(uuid, text)",
    "membership_set_firm_role(uuid, text)",
    "membership_revoke(uuid)",
)
_ROLE_CHECK = "IN ('firm_admin', 'practice_leader', 'quality_partner')"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE staff_invitations (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            email text NOT NULL CHECK (length(email) BETWEEN 3 AND 320),
            firm_role text NULL CHECK (firm_role {_ROLE_CHECK}),
            invited_by uuid NOT NULL,
            status text NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'accepted', 'revoked', 'expired')),
            expires_at timestamptz NOT NULL,
            accepted_by uuid NULL,
            accepted_at timestamptz NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, invited_by) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX staff_invitations_one_pending ON staff_invitations "
        "(tenant_id, lower(email)) WHERE status = 'pending'"
    )
    tenant_table(op, "staff_invitations")
    op.execute("REVOKE UPDATE, DELETE ON staff_invitations FROM abacus_app")
    insert_columns(
        op,
        "staff_invitations",
        ("id", "tenant_id", "email", "firm_role", "invited_by", "expires_at"),
    )
    op.execute(
        "GRANT UPDATE (status, accepted_by, accepted_at, expires_at) "
        "ON staff_invitations TO abacus_app"
    )
    op.execute(
        """
        CREATE TABLE staff_invitation_tokens (
            token_hash text PRIMARY KEY CHECK (token_hash ~ '^[0-9a-f]{64}$'),
            tenant_id uuid NOT NULL,
            invitation_id uuid NOT NULL UNIQUE,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp()
        )
        """
    )
    op.execute("REVOKE ALL ON staff_invitation_tokens FROM abacus_app")
    op.execute(
        """
        CREATE FUNCTION staff_invitation_token_set(p_invitation uuid, p_hash text) RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp
        SET statement_timeout = '5s'
        AS $$
        DECLARE v_tenant uuid := NULLIF(current_setting('app.tenant_id', true), '')::uuid;
        BEGIN
            IF v_tenant IS NULL OR NOT EXISTS (
                SELECT 1 FROM public.staff_invitations
                 WHERE id = p_invitation AND tenant_id = v_tenant
            ) THEN
                RAISE EXCEPTION 'unknown invitation';
            END IF;
            DELETE FROM public.staff_invitation_tokens WHERE invitation_id = p_invitation;
            IF p_hash IS NOT NULL THEN
                INSERT INTO public.staff_invitation_tokens (token_hash, tenant_id, invitation_id)
                VALUES (p_hash, v_tenant, p_invitation);
            END IF;
        END $$
        """
    )
    # The same lockout as client invitations (SPEC-015 Q4): 10 failures in an hour, 15 minutes.
    op.execute(
        """
        CREATE FUNCTION staff_invitation_token_find(p_hash text, p_identity text)
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
            RETURN QUERY SELECT t.tenant_id, t.invitation_id FROM public.staff_invitation_tokens t
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
        CREATE FUNCTION add_staff_membership(p_user uuid, p_role text) RETURNS text
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp
        SET statement_timeout = '5s'
        AS $$
        DECLARE v_tenant uuid := NULLIF(current_setting('app.tenant_id', true), '')::uuid;
                v_kind text;
        BEGIN
            IF v_tenant IS NULL THEN RAISE EXCEPTION 'no tenant'; END IF;
            IF p_role IS NOT NULL
               AND p_role NOT IN ('firm_admin', 'practice_leader', 'quality_partner') THEN
                RAISE EXCEPTION 'not a firm role' USING ERRCODE = 'check_violation';
            END IF;
            SELECT kind INTO v_kind FROM public.memberships
             WHERE tenant_id = v_tenant AND user_id = p_user FOR UPDATE;
            IF v_kind = 'client' THEN
                RETURN 'client_contact';
            ELSIF v_kind IS NULL THEN
                INSERT INTO public.memberships (tenant_id, user_id, firm_role, kind)
                VALUES (v_tenant, p_user, p_role, 'staff');
            ELSE
                UPDATE public.memberships
                   SET status = 'active', revoked_at = NULL, firm_role = p_role
                 WHERE tenant_id = v_tenant AND user_id = p_user;
            END IF;
            RETURN 'ok';
        END $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION membership_set_firm_role(p_user uuid, p_role text) RETURNS text
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp
        SET statement_timeout = '5s'
        AS $$
        DECLARE v_tenant uuid := NULLIF(current_setting('app.tenant_id', true), '')::uuid;
                v_current text;
                v_found boolean;
        BEGIN
            IF p_role IS NOT NULL
               AND p_role NOT IN ('firm_admin', 'practice_leader', 'quality_partner') THEN
                RAISE EXCEPTION 'not a firm role' USING ERRCODE = 'check_violation';
            END IF;
            SELECT true, firm_role INTO v_found, v_current FROM public.memberships
             WHERE tenant_id = v_tenant AND user_id = p_user
               AND kind = 'staff' AND status = 'active'
             FOR UPDATE;
            IF v_found IS NULL THEN RETURN 'not_found'; END IF;
            IF v_current = 'firm_admin' AND p_role IS DISTINCT FROM 'firm_admin' AND NOT EXISTS (
                SELECT 1 FROM public.memberships
                 WHERE tenant_id = v_tenant AND firm_role = 'firm_admin'
                   AND status = 'active' AND kind = 'staff' AND user_id <> p_user
            ) THEN
                RETURN 'last_admin';
            END IF;
            UPDATE public.memberships SET firm_role = p_role
             WHERE tenant_id = v_tenant AND user_id = p_user;
            RETURN 'ok';
        END $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION membership_revoke(p_user uuid) RETURNS text
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp
        SET statement_timeout = '5s'
        AS $$
        DECLARE v_tenant uuid := NULLIF(current_setting('app.tenant_id', true), '')::uuid;
                v_current text;
                v_found boolean;
        BEGIN
            SELECT true, firm_role INTO v_found, v_current FROM public.memberships
             WHERE tenant_id = v_tenant AND user_id = p_user
               AND kind = 'staff' AND status = 'active'
             FOR UPDATE;
            IF v_found IS NULL THEN RETURN 'not_found'; END IF;
            IF v_current = 'firm_admin' AND NOT EXISTS (
                SELECT 1 FROM public.memberships
                 WHERE tenant_id = v_tenant AND firm_role = 'firm_admin'
                   AND status = 'active' AND kind = 'staff' AND user_id <> p_user
            ) THEN
                RETURN 'last_admin';
            END IF;
            UPDATE public.memberships SET status = 'revoked', revoked_at = clock_timestamp()
             WHERE tenant_id = v_tenant AND user_id = p_user;
            RETURN 'ok';
        END $$
        """
    )
    for function in _FUNCTIONS:
        op.execute(f"REVOKE ALL ON FUNCTION {function} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {function} TO abacus_app")


def downgrade() -> None:
    for function in _FUNCTIONS:
        op.execute(f"DROP FUNCTION {function}")
    op.execute("DROP TABLE staff_invitation_tokens")
    op.execute("DROP TABLE staff_invitations")
