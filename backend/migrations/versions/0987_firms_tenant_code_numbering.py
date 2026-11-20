"""S51 CI fixes (TASK-8744; DEC-5734): a second firm with the same initials can be provisioned.

0921's `firms_tenant_code_default()` picks the first free `tnt_<initials><nn>` with a NOT EXISTS
probe on `firms`. `firms` has FORCE ROW LEVEL SECURITY and `provision_firm` sets `app.tenant_id`
to the new tenant before its insert, so the probe sees no other firm: every firm got `nn = 01`
and the second firm whose initials matched died on the `firms_tenant_code` unique index (CI:
"Pinned" after "Probe"). The unique index sees every tenant, so `provision_firm` now names the
code itself, `01` upward, and moves to the next number when that index refuses one; a
concurrent provision with the same initials waits on the index and then takes the next number.
Any other unique violation is raised as before. The trigger stays for inserts outside
`provision_firm` (its own test and seed paths); its NULL branch no longer runs from here.

Revision ID: 0987
Revises: 0986
"""

from __future__ import annotations

from alembic import op

revision = "0987"
down_revision = "0986"
branch_labels = None
depends_on = None

_NEW = r"""
    CREATE OR REPLACE FUNCTION provision_firm(
        p_name text, p_synthetic boolean, p_region text, p_time_zone text,
        p_idempotency_key text, p_operator text
    ) RETURNS uuid
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path = pg_catalog, public, pg_temp
    SET statement_timeout = '5s'
    AS $$

        DECLARE
            v_tenant uuid;
            v_previous text := current_setting('app.tenant_id', true);
            v_letters text;
            v_constraint text;

        BEGIN
            IF p_region IS DISTINCT FROM 'us' THEN
                RAISE EXCEPTION 'region % is not offered', p_region
                    USING ERRCODE = 'check_violation';
            END IF;
            SELECT r.tenant_id INTO v_tenant FROM public.firm_provisioning_requests r
             WHERE r.idempotency_key = p_idempotency_key;
            IF v_tenant IS NOT NULL THEN
                RETURN v_tenant;
            END IF;
            v_tenant := gen_random_uuid();
            PERFORM set_config('app.tenant_id', v_tenant::text, true);

            -- The initials rule of 0921's firms_tenant_code_default(), kept identical.
            SELECT coalesce(nullif(left(lower(regexp_replace(string_agg(left(w, 1), ''),
                                                             '[^a-zA-Z0-9]', '', 'g')), 3), ''),
                            'f')
              INTO v_letters
              FROM regexp_split_to_table(p_name, '\s+') AS w;
            FOR v_n IN 1..9999 LOOP
                BEGIN
                    INSERT INTO public.firms (tenant_id, name, synthetic, region, time_zone,
                                              tenant_code)
                    VALUES (v_tenant, p_name, p_synthetic, p_region, p_time_zone,
                            'tnt_' || v_letters || lpad(v_n::text, 2, '0'));
                    EXIT;
                EXCEPTION WHEN unique_violation THEN
                    GET STACKED DIAGNOSTICS v_constraint = CONSTRAINT_NAME;
                    IF v_constraint IS DISTINCT FROM 'firms_tenant_code' OR v_n = 9999 THEN
                        RAISE;
                    END IF;
                END;
            END LOOP;

            PERFORM set_config('app.tenant_id', coalesce(v_previous, ''), true);
            INSERT INTO public.firm_provisioning_requests (idempotency_key, tenant_id, operator)
            VALUES (p_idempotency_key, v_tenant, p_operator);
            RETURN v_tenant;
        END $$
"""

_OLD = r"""
    CREATE OR REPLACE FUNCTION provision_firm(
        p_name text, p_synthetic boolean, p_region text, p_time_zone text,
        p_idempotency_key text, p_operator text
    ) RETURNS uuid
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path = pg_catalog, public, pg_temp
    SET statement_timeout = '5s'
    AS $$

        DECLARE
            v_tenant uuid;
            v_previous text := current_setting('app.tenant_id', true);

        BEGIN
            IF p_region IS DISTINCT FROM 'us' THEN
                RAISE EXCEPTION 'region % is not offered', p_region
                    USING ERRCODE = 'check_violation';
            END IF;
            SELECT r.tenant_id INTO v_tenant FROM public.firm_provisioning_requests r
             WHERE r.idempotency_key = p_idempotency_key;
            IF v_tenant IS NOT NULL THEN
                RETURN v_tenant;
            END IF;
            v_tenant := gen_random_uuid();
            PERFORM set_config('app.tenant_id', v_tenant::text, true);

            INSERT INTO public.firms (tenant_id, name, synthetic, region, time_zone)
            VALUES (v_tenant, p_name, p_synthetic, p_region, p_time_zone);

            PERFORM set_config('app.tenant_id', coalesce(v_previous, ''), true);
            INSERT INTO public.firm_provisioning_requests (idempotency_key, tenant_id, operator)
            VALUES (p_idempotency_key, v_tenant, p_operator);
            RETURN v_tenant;
        END $$
"""


def upgrade() -> None:
    op.execute(_NEW)


def downgrade() -> None:
    op.execute(_OLD)
