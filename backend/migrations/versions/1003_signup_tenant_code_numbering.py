"""Sign-up names its tenant code (TASK-8870; DEC-5867), as provisioning does since 0987.

0921's `firms_tenant_code_default()` trigger picks the first free `tnt_<initials><nn>` with a NOT
EXISTS probe on `firms`, which has FORCE ROW LEVEL SECURITY: `firm_signup` (0032) sets
`app.tenant_id` to the new tenant before its insert, so the probe sees no other firm, every firm
gets `nn = 01`, and a second sign-up whose initials match an existing firm's dies on the
`firms_tenant_code` unique index (500 on POST /v1/signup). 0987 fixed `provision_firm` the same
way: the function names the code, `01` upward, and takes the next number when that index refuses
one. Any other unique violation is raised as before. The body is otherwise 0032's.

Revision ID: 1003
Revises: 1002
"""

from __future__ import annotations

from alembic import op

revision = "1003"
down_revision = "1002"
branch_labels = None
depends_on = None

_NEW = r"""
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

_OLD = r"""
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
            INSERT INTO public.firms (tenant_id, name, created_by, created_at_signup)
            VALUES (v_tenant, p_firm_name, v_user, true);
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
    op.execute(_NEW)


def downgrade() -> None:
    op.execute(_OLD)
