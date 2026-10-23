"""ED-011 and ED-009: gate facts in the human-only register; `security_admin` in staff functions.

**ED-011** (Q-02-T17, INV-1): three SPEC-025 gate facts join the human-only register.

`engagement.acceptance_recorded`, `engagement.letter_recorded` and `independence.declined` are
recorded by a person (SPEC-025 §14) but were missing from
`docs/architecture/human-only-actions.yaml`, so the `audit_events_human_only` trigger would have
accepted them written by an `agent` or `policy` actor. This redefines `abacus_human_only_actions()`
with the register as it now stands. `CREATE OR REPLACE` keeps 0098's EXECUTE grant to the app
role; the trigger reads the function on every insert, so it needs no change.

**ED-009** (P-10, DEC-21): 0080 added the firm role `security_admin` to the `memberships` and
`staff_invitations` checks, but 0033's definer functions `add_staff_membership` and
`membership_set_firm_role` still refused it ("not a firm role"), so accepting a `security_admin`
invitation or changing someone to it failed. Both are redefined with the four firm roles and
their bodies otherwise unchanged; `CREATE OR REPLACE` keeps their owner and grants.

Revision ID: 0127
Revises: 0115
"""

from __future__ import annotations

from alembic import op

revision = "0127"
down_revision = "0115"
branch_labels = None
depends_on = None

_ACTIONS = """ARRAY[
        'engagement.acceptance_recorded',
        'engagement.accepted',
        'engagement.letter_recorded',
        'evidence.accepted',
        'firm.ai_client_data_opted_in',
        'firm_export.approved',
        'going_concern.decided',
        'guidance_draft.approved',
        'independence.confirmed',
        'independence.declined',
        'legal_hold.placed',
        'materiality.decided',
        'procedure.concluded',
        'report.approved',
        'report.released',
        'review.decided',
        'review.released',
        'risk.approved',
        'sample.approved',
        'sign_off.recorded',
        'statement.approved'
    ]::text[]"""

_FIRM_ROLES = "('firm_admin', 'practice_leader', 'quality_partner', 'security_admin')"
_FIRM_ROLES_BEFORE = "('firm_admin', 'practice_leader', 'quality_partner')"

_ADD_STAFF_MEMBERSHIP = """
        CREATE OR REPLACE FUNCTION add_staff_membership(p_user uuid, p_role text) RETURNS text
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp
        SET statement_timeout = '5s'
        AS $$
        DECLARE v_tenant uuid := NULLIF(current_setting('app.tenant_id', true), '')::uuid;
                v_kind text;
        BEGIN
            IF v_tenant IS NULL THEN RAISE EXCEPTION 'no tenant'; END IF;
            IF p_role IS NOT NULL
               AND p_role NOT IN {roles} THEN
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

_SET_FIRM_ROLE = """
        CREATE OR REPLACE FUNCTION membership_set_firm_role(p_user uuid, p_role text) RETURNS text
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp
        SET statement_timeout = '5s'
        AS $$
        DECLARE v_tenant uuid := NULLIF(current_setting('app.tenant_id', true), '')::uuid;
                v_current text;
                v_found boolean;
        BEGIN
            IF p_role IS NOT NULL
               AND p_role NOT IN {roles} THEN
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

_BEFORE = """ARRAY[
        'engagement.accepted',
        'evidence.accepted',
        'firm.ai_client_data_opted_in',
        'firm_export.approved',
        'going_concern.decided',
        'guidance_draft.approved',
        'independence.confirmed',
        'legal_hold.placed',
        'materiality.decided',
        'procedure.concluded',
        'report.approved',
        'report.released',
        'review.decided',
        'review.released',
        'risk.approved',
        'sample.approved',
        'sign_off.recorded',
        'statement.approved'
    ]::text[]"""


def _define(actions: str) -> None:
    op.execute(
        "CREATE OR REPLACE FUNCTION abacus_human_only_actions() RETURNS text[] "
        "LANGUAGE sql IMMUTABLE PARALLEL SAFE "
        f"AS $$ SELECT {actions} $$"
    )


def _staff_functions(roles: str) -> None:
    op.execute(_ADD_STAFF_MEMBERSHIP.format(roles=roles))
    op.execute(_SET_FIRM_ROLE.format(roles=roles))


def upgrade() -> None:
    _define(_ACTIONS)
    _staff_functions(_FIRM_ROLES)


def downgrade() -> None:
    _staff_functions(_FIRM_ROLES_BEFORE)
    _define(_BEFORE)
