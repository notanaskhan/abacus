"""Engagement team management (SPEC-017; TASK-032 D1).

Role changes and removals of staff members go through these SECURITY DEFINER functions only, in
the session's firm; the application role keeps no UPDATE or DELETE on `engagement_members`. Both
refuse to leave an engagement without an engagement partner (Q2), so the rule holds even if a
caller forgets it.

Revision ID: 0027
Revises: 0026
"""

from __future__ import annotations

from alembic import op

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None

_FUNCTIONS = ("team_member_set_role(uuid, uuid, text)", "team_member_remove(uuid, uuid)")


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION team_member_set_role(p_engagement uuid, p_user uuid, p_role text)
        RETURNS text
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp
        SET statement_timeout = '5s'
        AS $$
        DECLARE v_tenant uuid := NULLIF(current_setting('app.tenant_id', true), '')::uuid;
                v_current text;
        BEGIN
            IF p_role NOT IN ('engagement_partner', 'manager', 'senior', 'staff', 'reviewer') THEN
                RAISE EXCEPTION 'not a staff role' USING ERRCODE = 'check_violation';
            END IF;
            SELECT role INTO v_current FROM public.engagement_members
             WHERE tenant_id = v_tenant AND engagement_id = p_engagement AND user_id = p_user
             FOR UPDATE;
            IF v_current IS NULL
               OR v_current NOT IN ('engagement_partner', 'manager', 'senior', 'staff', 'reviewer')
            THEN
                RETURN 'not_found';
            END IF;
            IF v_current = 'engagement_partner' AND p_role <> 'engagement_partner' AND NOT EXISTS (
                SELECT 1 FROM public.engagement_members
                 WHERE tenant_id = v_tenant AND engagement_id = p_engagement
                   AND role = 'engagement_partner' AND user_id <> p_user
            ) THEN
                RETURN 'last_partner';
            END IF;
            UPDATE public.engagement_members SET role = p_role
             WHERE tenant_id = v_tenant AND engagement_id = p_engagement AND user_id = p_user;
            RETURN 'ok';
        END $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION team_member_remove(p_engagement uuid, p_user uuid)
        RETURNS text
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp
        SET statement_timeout = '5s'
        AS $$
        DECLARE v_tenant uuid := NULLIF(current_setting('app.tenant_id', true), '')::uuid;
                v_current text;
        BEGIN
            SELECT role INTO v_current FROM public.engagement_members
             WHERE tenant_id = v_tenant AND engagement_id = p_engagement AND user_id = p_user
             FOR UPDATE;
            IF v_current IS NULL
               OR v_current NOT IN ('engagement_partner', 'manager', 'senior', 'staff', 'reviewer')
            THEN
                RETURN 'not_found';
            END IF;
            IF v_current = 'engagement_partner' AND NOT EXISTS (
                SELECT 1 FROM public.engagement_members
                 WHERE tenant_id = v_tenant AND engagement_id = p_engagement
                   AND role = 'engagement_partner' AND user_id <> p_user
            ) THEN
                RETURN 'last_partner';
            END IF;
            DELETE FROM public.engagement_members
             WHERE tenant_id = v_tenant AND engagement_id = p_engagement AND user_id = p_user;
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
