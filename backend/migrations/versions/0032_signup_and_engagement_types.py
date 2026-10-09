"""Self-serve sign-up and engagement types (SPEC-024; TASK-040).

- `signup_codes` (global): founder-issued, single-use, expiring, stored only as hashes (D2).
- `signup_attempts` (global): every attempt, for rate limits (amendment 2) and review; holds
  only fingerprints of the identity and the client address.
- `firm_signup(...)`: the one way the app creates a firm, as one reviewed SECURITY DEFINER
  transaction: rate limit, spend the code, provision the user,
  create the firm and its first firm administrator. It answers with an outcome code, so a
  refusal still records its attempt.
- `firms.created_by`; engagement types; templates tagged at creation with the types they serve
  (D3; templates stay insert-only).

Revision ID: 0032
Revises: 0031
"""

from __future__ import annotations

from alembic import op

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None

_FUNCTION = "firm_signup(text, text, text, text, text, text, text, text)"
TYPES = "('audit', 'review', 'compilation', 'agreed_upon_procedures')"


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE signup_codes (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            code_hash text NOT NULL UNIQUE CHECK (code_hash ~ '^[0-9a-f]{64}$'),
            note text NOT NULL CHECK (length(note) BETWEEN 1 AND 200),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            expires_at timestamptz NOT NULL,
            used_at timestamptz NULL,
            used_tenant_id uuid NULL,
            CHECK ((used_at IS NULL) = (used_tenant_id IS NULL))
        )
        """
    )
    op.execute(
        """
        CREATE TABLE signup_attempts (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            identity_hash text NOT NULL CHECK (identity_hash ~ '^[0-9a-f]{64}$'),
            address_hash text NOT NULL CHECK (address_hash ~ '^[0-9a-f]{64}$'),
            outcome text NOT NULL CHECK (
                outcome IN ('created', 'invalid_code', 'already_member', 'rate_limited')
            ),
            at timestamptz NOT NULL DEFAULT clock_timestamp()
        )
        """
    )
    op.execute("CREATE INDEX signup_attempts_identity ON signup_attempts (identity_hash, at)")
    op.execute("CREATE INDEX signup_attempts_address ON signup_attempts (address_hash, at)")
    op.execute("REVOKE ALL ON signup_codes, signup_attempts FROM abacus_app")
    op.execute(
        "ALTER TABLE firms ADD COLUMN created_by uuid NULL, "
        "ADD COLUMN created_at_signup boolean NOT NULL DEFAULT false"
    )
    op.execute(
        f"ALTER TABLE engagements DROP CONSTRAINT engagements_type_check, "
        f"ADD CONSTRAINT engagements_type_check CHECK (type IN {TYPES})"
    )
    op.execute(
        "ALTER TABLE methodology_templates ADD COLUMN engagement_types text[] NOT NULL "
        "DEFAULT '{audit}' CHECK (cardinality(engagement_types) BETWEEN 1 AND 4 "
        f"AND engagement_types <@ ARRAY{TYPES.replace('(', '[').replace(')', ']')}::text[])"
    )
    op.execute("GRANT INSERT (type) ON engagements TO abacus_app")
    op.execute("GRANT INSERT (engagement_types) ON methodology_templates TO abacus_app")
    op.execute(
        """
        CREATE FUNCTION firm_signup(
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
    )
    op.execute(f"REVOKE ALL ON FUNCTION {_FUNCTION} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {_FUNCTION} TO abacus_app")


def downgrade() -> None:
    op.execute(f"DROP FUNCTION {_FUNCTION}")
    op.execute("REVOKE INSERT (engagement_types) ON methodology_templates FROM abacus_app")
    op.execute("ALTER TABLE methodology_templates DROP COLUMN engagement_types")
    op.execute(
        "ALTER TABLE engagements DROP CONSTRAINT engagements_type_check, "
        "ADD CONSTRAINT engagements_type_check CHECK (type IN ('audit'))"
    )
    op.execute("ALTER TABLE firms DROP COLUMN created_at_signup, DROP COLUMN created_by")
    op.execute("DROP TABLE signup_attempts")
    op.execute("DROP TABLE signup_codes")
