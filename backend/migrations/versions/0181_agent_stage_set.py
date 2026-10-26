"""Q-02-T07: the staff route sets an agent's stage through one SECURITY DEFINER function.

`agent_stages` (0056) stays read-only to the application role: the founder's ops command wrote
through the owner role, and the staff route (`PUT /v1/platform/agent-stages/{firm_id}/{agent_id}`)
needs the same write without that role. `agent_stage_set(tenant, agent, stage, staff, note)`
appends the stage row and refuses `live` until the firm has had at least 50 shadow runs of the
agent over 14 days (SPEC-036 Q1), raising `stage_not_ready`. It runs only inside the firm's own
transaction (`app.tenant_id` must name the firm), where the caller's unit of work records the
`agent_stage.changed` audit event and the boundary event with it. Only the application role may
execute it; the route admits only platform staff (the STAFF marker).

Revision ID: 0181
Revises: 0192
"""

from __future__ import annotations

from alembic import op

revision = "0181"
down_revision = "0192"
branch_labels = None
depends_on = None

_SIGNATURE = "agent_stage_set(uuid, text, text, text, text)"


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION agent_stage_set(
            p_tenant uuid, p_agent text, p_stage text, p_staff text, p_note text
        )
        RETURNS uuid
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        DECLARE
            v_id uuid;
            v_runs integer;
            v_first timestamptz;
        BEGIN
            IF p_staff IS NULL OR p_staff !~ '^staff:[0-9a-f-]{36}$' THEN
                RAISE EXCEPTION 'staff_required' USING ERRCODE = 'insufficient_privilege';
            END IF;
            -- Only inside the firm's own transaction: the caller's unit of work set the tenant.
            IF current_setting('app.tenant_id', true) IS DISTINCT FROM p_tenant::text THEN
                RAISE EXCEPTION 'tenant_mismatch' USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF NOT EXISTS (SELECT 1 FROM public.firms WHERE tenant_id = p_tenant) THEN
                RAISE EXCEPTION 'firm_not_found' USING ERRCODE = 'no_data_found';
            END IF;
            IF p_stage = 'live' THEN
                SELECT count(*), min(started_at) INTO v_runs, v_first
                  FROM public.agent_runs
                 WHERE tenant_id = p_tenant AND agent_id = p_agent AND shadow;
                IF v_runs < 50 OR v_first IS NULL
                   OR v_first > clock_timestamp() - interval '14 days' THEN
                    RAISE EXCEPTION 'stage_not_ready' USING ERRCODE = 'check_violation';
                END IF;
            END IF;
            INSERT INTO public.agent_stages (tenant_id, agent_id, stage, changed_by, note)
            VALUES (p_tenant, p_agent, p_stage, p_staff, btrim(p_note))
            RETURNING id INTO v_id;
            RETURN v_id;
        END $$
        """
    )
    op.execute(f"REVOKE ALL ON FUNCTION {_SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {_SIGNATURE} TO abacus_app")


def downgrade() -> None:
    op.execute(f"DROP FUNCTION {_SIGNATURE}")
