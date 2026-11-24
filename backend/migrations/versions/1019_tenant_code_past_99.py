"""Tenant codes past 99 (TASK-8965; DEC-5944): `lpad` truncates, so the 100th firm hung.

0921's `firms_tenant_code_default()` and 0987's `provision_firm` number codes
`tnt_<initials><nn>` with `lpad(n::text, 2, '0')`. `lpad` pads AND truncates to the length given:
`lpad('100', 2, '0')` is `'10'`. With `tnt_fx01` to `tnt_fx99` taken, the trigger's next code
was `tnt_fx10` again for every n, so its loop never ended: the INSERT ran at full CPU holding its
locks until something killed it. Every firm `Seeder.firm` makes is named `Firm x<hex>` (initials
`fx`), so the 100th seeded firm in one test database hung its CI shard until the job's timeout.
`provision_firm` mapped 100 to 9999 onto taken codes the same way, so the 100th firm with the
same initials could never be provisioned (statement timeout, or the unique violation at 9999).

1003's `firm_signup` (TASK-8870) numbers sign-up codes the same way and had the same flaw.

All three now pad to two digits and keep longer numbers whole (`tnt_fx100`), which the tenant code
pattern `^tnt_[a-z0-9-]{2,40}$` already allows. Nothing else in any of them changes. (Written as
1003 on the ci-speed branch, #2475; renumbered after S53's 1010 to 1018.)

Revision ID: 1019
Revises: 1018
"""

from __future__ import annotations

from alembic import op

revision = "1019"
down_revision = "1018"
branch_labels = None
depends_on = None

_TRIGGER_NEW = r"""
    CREATE OR REPLACE FUNCTION firms_tenant_code_default() RETURNS trigger
    LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
    DECLARE
        v_letters text;
        v_n integer := 1;
    BEGIN
        IF NEW.tenant_code IS NOT NULL THEN
            RETURN NEW;
        END IF;
        SELECT coalesce(nullif(left(lower(regexp_replace(string_agg(left(w, 1), ''),
                                                         '[^a-zA-Z0-9]', '', 'g')), 3), ''),
                        'f')
          INTO v_letters
          FROM regexp_split_to_table(NEW.name, '\s+') AS w;
        LOOP
            NEW.tenant_code := 'tnt_' || v_letters
                || lpad(v_n::text, greatest(2, length(v_n::text)), '0');
            EXIT WHEN NOT EXISTS (SELECT 1 FROM public.firms f
                                   WHERE f.tenant_code = NEW.tenant_code);
            v_n := v_n + 1;
        END LOOP;
        RETURN NEW;
    END $$
"""

_TRIGGER_OLD = r"""
    CREATE OR REPLACE FUNCTION firms_tenant_code_default() RETURNS trigger
    LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
    DECLARE
        v_letters text;
        v_n integer := 1;
    BEGIN
        IF NEW.tenant_code IS NOT NULL THEN
            RETURN NEW;
        END IF;
        SELECT coalesce(nullif(left(lower(regexp_replace(string_agg(left(w, 1), ''),
                                                         '[^a-zA-Z0-9]', '', 'g')), 3), ''),
                        'f')
          INTO v_letters
          FROM regexp_split_to_table(NEW.name, '\s+') AS w;
        LOOP
            NEW.tenant_code := 'tnt_' || v_letters || lpad(v_n::text, 2, '0');
            EXIT WHEN NOT EXISTS (SELECT 1 FROM public.firms f
                                   WHERE f.tenant_code = NEW.tenant_code);
            v_n := v_n + 1;
        END LOOP;
        RETURN NEW;
    END $$
"""

_PROVISION_NEW = r"""
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
                            'tnt_' || v_letters
                            || lpad(v_n::text, greatest(2, length(v_n::text)), '0'));
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

_PROVISION_OLD = r"""
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


_SIGNUP_NEW = r"""
        CREATE OR REPLACE FUNCTION firm_signup(
            p_code_hash text, p_identity_hash text, p_address_hash text,
            p_issuer text, p_subject text, p_email text, p_display_name text, p_firm_name text
        ) RETURNS TABLE (outcome text, tenant_id uuid)
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp
        SET statement_timeout = '5s'
        AS $$
        DECLARE v_code uuid;
                v_user uuid;
                v_tenant uuid;
                v_previous text := current_setting('app.tenant_id', true);
                v_letters text;
                v_constraint text;
        BEGIN
            -- Amendment 2: at most 5 failed attempts per identity and 20 per address an hour.
            IF (SELECT count(*) FROM public.signup_attempts a
                 WHERE a.identity_hash = p_identity_hash AND a.outcome <> 'created'
                   AND a.at > clock_timestamp() - interval '1 hour') >= 5
               OR (SELECT count(*) FROM public.signup_attempts a
                    WHERE a.address_hash = p_address_hash AND a.outcome <> 'created'
                      AND a.at > clock_timestamp() - interval '1 hour') >= 20 THEN
                INSERT INTO public.signup_attempts (identity_hash, address_hash, outcome)
                VALUES (p_identity_hash, p_address_hash, 'rate_limited');
                RETURN QUERY SELECT 'rate_limited'::text, NULL::uuid;
                RETURN;
            END IF;
            SELECT c.id INTO v_code FROM public.signup_codes c
             WHERE c.code_hash = p_code_hash AND c.used_at IS NULL
               AND c.expires_at > clock_timestamp()
             FOR UPDATE;
            IF v_code IS NULL THEN
                INSERT INTO public.signup_attempts (identity_hash, address_hash, outcome)
                VALUES (p_identity_hash, p_address_hash, 'invalid_code');
                RETURN QUERY SELECT 'invalid_code'::text, NULL::uuid;
                RETURN;
            END IF;
            -- Staff of another firm are refused by the service before this call: memberships sit
            -- behind forced row-level security, which this function (as the owner) can't see
            -- across firms; the identity role (BYPASSRLS) reads them there.
            SELECT u.id INTO v_user FROM public.users u
             WHERE u.idp_issuer = p_issuer AND u.idp_subject = p_subject;
            IF v_user IS NULL THEN
                INSERT INTO public.users (idp_issuer, idp_subject, email, display_name)
                VALUES (p_issuer, p_subject, p_email, p_display_name)
                RETURNING id INTO v_user;
            END IF;
            v_tenant := gen_random_uuid();
            -- The new firm's rows pass its own row-level security; the caller's setting returns.
            PERFORM set_config('app.tenant_id', v_tenant::text, true);
            -- 1003: the code is named here, as provision_firm does since 0987 (the trigger's
            -- probe can't see other firms behind forced row-level security).
            SELECT coalesce(nullif(left(lower(regexp_replace(string_agg(left(w, 1), ''),
                                                             '[^a-zA-Z0-9]', '', 'g')), 3), ''),
                            'f')
              INTO v_letters
              FROM regexp_split_to_table(p_firm_name, '\s+') AS w;
            FOR v_n IN 1..9999 LOOP
                BEGIN
                    INSERT INTO public.firms (tenant_id, name, created_by, created_at_signup,
                                              tenant_code)
                    VALUES (v_tenant, p_firm_name, v_user, true,
                            'tnt_' || v_letters
                            || lpad(v_n::text, greatest(2, length(v_n::text)), '0'));
                    EXIT;
                EXCEPTION WHEN unique_violation THEN
                    GET STACKED DIAGNOSTICS v_constraint = CONSTRAINT_NAME;
                    IF v_constraint IS DISTINCT FROM 'firms_tenant_code' OR v_n = 9999 THEN
                        RAISE;
                    END IF;
                END;
            END LOOP;
            INSERT INTO public.memberships (tenant_id, user_id, firm_role, kind)
            VALUES (v_tenant, v_user, 'firm_admin', 'staff');
            PERFORM set_config('app.tenant_id', coalesce(v_previous, ''), true);
            UPDATE public.signup_codes SET used_at = clock_timestamp(), used_tenant_id = v_tenant
             WHERE id = v_code;
            INSERT INTO public.signup_attempts (identity_hash, address_hash, outcome)
            VALUES (p_identity_hash, p_address_hash, 'created');
            RETURN QUERY SELECT 'created'::text, v_tenant;
        END $$
"""

# 1003's body, restored on downgrade.
_SIGNUP_OLD = r"""
        CREATE OR REPLACE FUNCTION firm_signup(
            p_code_hash text, p_identity_hash text, p_address_hash text,
            p_issuer text, p_subject text, p_email text, p_display_name text, p_firm_name text
        ) RETURNS TABLE (outcome text, tenant_id uuid)
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp
        SET statement_timeout = '5s'
        AS $$
        DECLARE v_code uuid;
                v_user uuid;
                v_tenant uuid;
                v_previous text := current_setting('app.tenant_id', true);
                v_letters text;
                v_constraint text;
        BEGIN
            -- Amendment 2: at most 5 failed attempts per identity and 20 per address an hour.
            IF (SELECT count(*) FROM public.signup_attempts a
                 WHERE a.identity_hash = p_identity_hash AND a.outcome <> 'created'
                   AND a.at > clock_timestamp() - interval '1 hour') >= 5
               OR (SELECT count(*) FROM public.signup_attempts a
                    WHERE a.address_hash = p_address_hash AND a.outcome <> 'created'
                      AND a.at > clock_timestamp() - interval '1 hour') >= 20 THEN
                INSERT INTO public.signup_attempts (identity_hash, address_hash, outcome)
                VALUES (p_identity_hash, p_address_hash, 'rate_limited');
                RETURN QUERY SELECT 'rate_limited'::text, NULL::uuid;
                RETURN;
            END IF;
            SELECT c.id INTO v_code FROM public.signup_codes c
             WHERE c.code_hash = p_code_hash AND c.used_at IS NULL
               AND c.expires_at > clock_timestamp()
             FOR UPDATE;
            IF v_code IS NULL THEN
                INSERT INTO public.signup_attempts (identity_hash, address_hash, outcome)
                VALUES (p_identity_hash, p_address_hash, 'invalid_code');
                RETURN QUERY SELECT 'invalid_code'::text, NULL::uuid;
                RETURN;
            END IF;
            -- Staff of another firm are refused by the service before this call: memberships sit
            -- behind forced row-level security, which this function (as the owner) can't see
            -- across firms; the identity role (BYPASSRLS) reads them there.
            SELECT u.id INTO v_user FROM public.users u
             WHERE u.idp_issuer = p_issuer AND u.idp_subject = p_subject;
            IF v_user IS NULL THEN
                INSERT INTO public.users (idp_issuer, idp_subject, email, display_name)
                VALUES (p_issuer, p_subject, p_email, p_display_name)
                RETURNING id INTO v_user;
            END IF;
            v_tenant := gen_random_uuid();
            -- The new firm's rows pass its own row-level security; the caller's setting returns.
            PERFORM set_config('app.tenant_id', v_tenant::text, true);
            -- 1003: the code is named here, as provision_firm does since 0987 (the trigger's
            -- probe can't see other firms behind forced row-level security).
            SELECT coalesce(nullif(left(lower(regexp_replace(string_agg(left(w, 1), ''),
                                                             '[^a-zA-Z0-9]', '', 'g')), 3), ''),
                            'f')
              INTO v_letters
              FROM regexp_split_to_table(p_firm_name, '\s+') AS w;
            FOR v_n IN 1..9999 LOOP
                BEGIN
                    INSERT INTO public.firms (tenant_id, name, created_by, created_at_signup,
                                              tenant_code)
                    VALUES (v_tenant, p_firm_name, v_user, true,
                            'tnt_' || v_letters || lpad(v_n::text, 2, '0'));
                    EXIT;
                EXCEPTION WHEN unique_violation THEN
                    GET STACKED DIAGNOSTICS v_constraint = CONSTRAINT_NAME;
                    IF v_constraint IS DISTINCT FROM 'firms_tenant_code' OR v_n = 9999 THEN
                        RAISE;
                    END IF;
                END;
            END LOOP;
            INSERT INTO public.memberships (tenant_id, user_id, firm_role, kind)
            VALUES (v_tenant, v_user, 'firm_admin', 'staff');
            PERFORM set_config('app.tenant_id', coalesce(v_previous, ''), true);
            UPDATE public.signup_codes SET used_at = clock_timestamp(), used_tenant_id = v_tenant
             WHERE id = v_code;
            INSERT INTO public.signup_attempts (identity_hash, address_hash, outcome)
            VALUES (p_identity_hash, p_address_hash, 'created');
            RETURN QUERY SELECT 'created'::text, v_tenant;
        END $$
"""


def upgrade() -> None:
    op.execute(_TRIGGER_NEW)
    op.execute(_PROVISION_NEW)
    op.execute(_SIGNUP_NEW)


def downgrade() -> None:
    op.execute(_SIGNUP_OLD)
    op.execute(_PROVISION_OLD)
    op.execute(_TRIGGER_OLD)
