"""The provisioning workflow's own writers (Q-01-T45 patch points; ADR-156; F-03-T28).

- `plan_modules`: which modules a plan holds, with its seats and agent minutes. It is global and
  set by operators through `set_plan_module` (EXECUTE to `abacus_ops` only), so plan contents are
  data, never code (AGENTS.md 16).
- `apply_plan_entitlements(tenant, plan, operator)`: writes a newly provisioned firm's
  `tenant_entitlements` rows from its plan, valid from the kernel's business date (Central).
  It refuses a firm that wasn't provisioned through `provision_firm`, and one that already holds
  entitlement rows, so the app role can't use it to widen an existing firm. Later changes stay
  with the operator's `make entitlement`.
- `invite_first_admin(tenant, email, operator)`: a firm-administrator staff invitation issued by
  the operator, allowed only while the firm has no active member. Such a row names the operator
  instead of a member (`issued_by_operator`). Every other invitation still names the member who
  sent it. 14 days, as every staff invitation.

Revision ID: 0107
Revises: 0106
"""

from __future__ import annotations

from alembic import op

revision = "0107"
down_revision = "0106"
branch_labels = None
depends_on = None

_MODULES = (
    "('attest', 'internal_audit', 'group_audit', 'statements_studio', 'office_addins', 'insights')"
)


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE plan_modules (
            plan_code text NOT NULL REFERENCES plans (code),
            module text NOT NULL CHECK (module IN {_MODULES}),
            seats integer NULL CHECK (seats >= 0),
            agent_minutes_allowance integer NULL CHECK (agent_minutes_allowance >= 0),
            set_by text NOT NULL CHECK (length(set_by) BETWEEN 1 AND 100),
            set_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            PRIMARY KEY (plan_code, module)
        )
        """
    )
    op.execute("REVOKE ALL ON plan_modules FROM PUBLIC, abacus_app")

    op.execute(
        """
        CREATE FUNCTION set_plan_module(
            p_plan text, p_module text, p_seats integer, p_minutes integer, p_operator text
        ) RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            INSERT INTO public.plan_modules
                (plan_code, module, seats, agent_minutes_allowance, set_by)
            VALUES (p_plan, p_module, p_seats, p_minutes, p_operator)
            ON CONFLICT (plan_code, module) DO UPDATE SET seats = EXCLUDED.seats,
                agent_minutes_allowance = EXCLUDED.agent_minutes_allowance,
                set_by = EXCLUDED.set_by, set_at = clock_timestamp();
        END $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION apply_plan_entitlements(p_tenant uuid, p_plan text, p_operator text)
        RETURNS integer
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        DECLARE
            v_rows integer;
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM public.firm_provisioning_requests r
                            WHERE r.tenant_id = p_tenant) THEN
                RAISE EXCEPTION 'firm % was not provisioned', p_tenant
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF EXISTS (SELECT 1 FROM public.tenant_entitlements e
                        WHERE e.tenant_id = p_tenant) THEN
                RETURN 0;  -- applied already (a retried activity), or set by an operator since
            END IF;
            INSERT INTO public.tenant_entitlements (tenant_id, module, plan_code, enabled, seats,
                agent_minutes_allowance, valid_from, set_by)
            SELECT p_tenant, m.module, m.plan_code, true, m.seats, m.agent_minutes_allowance,
                   (clock_timestamp() AT TIME ZONE 'America/Chicago')::date, p_operator
              FROM public.plan_modules m WHERE m.plan_code = p_plan;
            GET DIAGNOSTICS v_rows = ROW_COUNT;
            RETURN v_rows;
        END $$
        """
    )

    op.execute("ALTER TABLE staff_invitations ALTER COLUMN invited_by DROP NOT NULL")
    op.execute(
        "ALTER TABLE staff_invitations ADD COLUMN issued_by_operator text NULL "
        "CHECK (issued_by_operator ~ '^operator:[a-z][a-z0-9._-]{0,60}$'), "
        "ADD CONSTRAINT staff_invitations_one_sender "
        "CHECK ((invited_by IS NULL) <> (issued_by_operator IS NULL))"
    )
    op.execute(
        """
        CREATE FUNCTION invite_first_admin(p_tenant uuid, p_email text, p_operator text)
        RETURNS uuid
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        DECLARE
            v_id uuid;
        BEGIN
            IF EXISTS (SELECT 1 FROM public.memberships m
                        WHERE m.tenant_id = p_tenant AND m.status = 'active') THEN
                RAISE EXCEPTION 'firm % already has members', p_tenant
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            SELECT i.id INTO v_id FROM public.staff_invitations i
             WHERE i.tenant_id = p_tenant AND lower(i.email) = lower(p_email)
               AND i.status = 'pending' AND i.issued_by_operator IS NOT NULL;
            IF FOUND THEN
                RETURN v_id;  -- a retried activity: the same invitation
            END IF;
            INSERT INTO public.staff_invitations (tenant_id, email, firm_role, invited_by,
                issued_by_operator, expires_at)
            VALUES (p_tenant, p_email, 'firm_admin', NULL, p_operator,
                    clock_timestamp() + interval '14 days')
            RETURNING id INTO v_id;
            RETURN v_id;
        END $$
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION set_plan_module(text, text, integer, integer, text) FROM PUBLIC"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION set_plan_module(text, text, integer, integer, text) "
        "TO abacus_ops"
    )
    for signature in (
        "apply_plan_entitlements(uuid, text, text)",
        "invite_first_admin(uuid, text, text)",
    ):
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO abacus_app")


def downgrade() -> None:
    op.execute("DROP FUNCTION invite_first_admin(uuid, text, text)")
    op.execute("DELETE FROM staff_invitations WHERE issued_by_operator IS NOT NULL")
    op.execute(
        "ALTER TABLE staff_invitations DROP CONSTRAINT staff_invitations_one_sender, "
        "DROP COLUMN issued_by_operator"
    )
    op.execute("ALTER TABLE staff_invitations ALTER COLUMN invited_by SET NOT NULL")
    op.execute("DROP FUNCTION apply_plan_entitlements(uuid, text, text)")
    op.execute("DROP FUNCTION set_plan_module(text, text, integer, integer, text)")
    op.execute("DROP TABLE plan_modules")
