"""P-08-T17: the portal's second step (SPEC-320 AC-10, AC-11; DEC-34; ADR-168; DEC-250).

Three new global tables with no app or identity-role privileges, reached only through SECURITY
DEFINER functions (as 0116's sign-in tables are), and one tenant table:

- `mfa_factors`: a person's TOTP factor at the portal's identity provider (WorkOS), by its ids
  only; the secret is never stored. `enrolled_at` is null while setup waits for its first code. A
  factor belongs to the person, not the firm (ADR-002), like `auth_sessions`, so its second-step
  guesses are counted here, across every firm: three wrong ones in 15 minutes lock it for 15.
- `mfa_backup_codes`: SHA-256 of each of the person's 8 backup codes (80 random bits each), and
  when each was used. A new enrolment replaces them.
- `trusted_devices`: per firm and person, the SHA-256 of a `__Host-` device cookie, its expiry
  (the firm's days, 30 at most, set by `portal_device_trust`) and its revocation.
- `portal_security_policies` (tenant, forced RLS, read-only to the app until G-02 adds its
  writer): the firm's stricter-only extension of the floor. `mfa_for_all_client_users` can only
  widen it; `trusted_device_days` can only shorten the 30-day ceiling.

`sign_in_challenges` gains the second-step token (SHA-256, 5 minutes, single use, `verify` or
`setup`). A right email code does not reset the factor's guesses; the third wrong one also sets the
firm's 15-minute `sign_in_locks.locked_until` for the email.

Definers: `portal_mfa_begin`, `portal_mfa_attempt` (each guess counted before it is compared),
`portal_mfa_missed`, `portal_mfa_backup_use`, `portal_mfa_setup_claim`,
`portal_mfa_factor_pending`, `portal_mfa_enrol`, `portal_mfa_complete`, `portal_mfa_enrolled`,
`portal_session_mark_mfa`, `portal_device_trust`, `portal_device_check` and
`portal_access_revoke`.

Revision ID: 0133
Revises: 0116
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import tenant_table

revision = "0133"
down_revision = "0116"
branch_labels = None
depends_on = None

_FUNCTIONS = (
    "portal_mfa_begin(uuid, text, text, integer)",
    "portal_mfa_attempt(text, text, text, integer, integer)",
    "portal_mfa_missed(text, integer, integer)",
    "portal_mfa_backup_use(uuid, text)",
    "portal_mfa_setup_claim(text, text)",
    "portal_mfa_factor_pending(uuid, text, text)",
    "portal_mfa_enrol(text, text, text[])",
    "portal_mfa_complete(text)",
    "portal_mfa_enrolled(uuid)",
    "portal_session_mark_mfa(uuid, uuid)",
    "portal_device_trust(uuid, uuid, text, integer, text)",
    "portal_device_check(uuid, uuid, text, integer)",
    "portal_access_revoke(uuid, uuid)",
)
_SHA = "~ '^[0-9a-f]{64}$'"


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE mfa_factors (
            user_id uuid PRIMARY KEY REFERENCES users (id),
            provider text NOT NULL DEFAULT 'workos' CHECK (provider IN ('workos')),
            provider_user_ref text NOT NULL CHECK (length(provider_user_ref) BETWEEN 1 AND 200),
            factor_ref text NOT NULL CHECK (length(factor_ref) BETWEEN 1 AND 200),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            enrolled_at timestamptz NULL,
            mfa_attempts integer NOT NULL DEFAULT 0 CHECK (mfa_attempts >= 0),
            mfa_window_until timestamptz NULL,
            mfa_locked_until timestamptz NULL
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE mfa_backup_codes (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id uuid NOT NULL REFERENCES users (id),
            code_sha256 text NOT NULL CHECK (code_sha256 {_SHA}),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            used_at timestamptz NULL,
            UNIQUE (user_id, code_sha256)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE trusted_devices (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES firms (tenant_id),
            user_id uuid NOT NULL REFERENCES users (id),
            token_sha256 text NOT NULL UNIQUE CHECK (token_sha256 {_SHA}),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            expires_at timestamptz NOT NULL,
            revoked_at timestamptz NULL,
            revoked_reason text NULL CHECK (revoked_reason IN ('access_changed', 'mfa_reset')),
            ua_family text NULL CHECK (length(ua_family) BETWEEN 1 AND 40),
            CHECK (expires_at > created_at),
            CHECK ((revoked_at IS NULL) = (revoked_reason IS NULL))
        )
        """
    )
    op.execute(
        "CREATE INDEX trusted_devices_live ON trusted_devices (tenant_id, user_id) "
        "WHERE revoked_at IS NULL"
    )
    for table in ("mfa_factors", "mfa_backup_codes", "trusted_devices"):
        op.execute(f"REVOKE ALL ON {table} FROM PUBLIC, abacus_app")

    op.execute(
        """
        CREATE TABLE portal_security_policies (
            tenant_id uuid PRIMARY KEY REFERENCES firms (tenant_id),
            mfa_for_all_client_users boolean NOT NULL DEFAULT false,
            trusted_device_days smallint NOT NULL DEFAULT 30
                CHECK (trusted_device_days BETWEEN 0 AND 30),
            version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
            updated_by uuid NULL,
            updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
        )
        """
    )
    tenant_table(op, "portal_security_policies")
    # G-02 serves the setting (`portal_security.manage`) and grants its writer then.
    op.execute("REVOKE INSERT, UPDATE, DELETE ON portal_security_policies FROM abacus_app")

    op.execute(
        f"""
        ALTER TABLE sign_in_challenges
            ADD COLUMN mfa_token_sha256 text NULL UNIQUE CHECK (mfa_token_sha256 {_SHA}),
            ADD COLUMN mfa_kind text NULL CHECK (mfa_kind IN ('verify', 'setup')),
            ADD COLUMN mfa_expires_at timestamptz NULL,
            ADD COLUMN mfa_setup_at timestamptz NULL,
            ADD COLUMN mfa_used_at timestamptz NULL,
            ADD CONSTRAINT sign_in_challenges_mfa CHECK (
                (mfa_token_sha256 IS NULL) = (mfa_kind IS NULL)
                AND (mfa_token_sha256 IS NULL) = (mfa_expires_at IS NULL)
                AND (mfa_token_sha256 IS NULL OR user_id IS NOT NULL))
        """
    )

    # The right email code, for a person the floor covers: the challenge is used (as
    # `portal_sign_in_consume`, which also clears the code guesses) and a second-step token starts.
    # The factor's second-step guesses are not reset here. False when a concurrent verify used it
    # first.
    op.execute(
        """
        CREATE FUNCTION portal_mfa_begin(
            p_id uuid, p_token_sha256 text, p_kind text, p_seconds integer
        ) RETURNS boolean
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        DECLARE
            v_challenge record;
        BEGIN
            UPDATE public.sign_in_challenges SET consumed_at = clock_timestamp(),
                code_salt = NULL, code_digest = NULL, mfa_token_sha256 = p_token_sha256,
                mfa_kind = p_kind,
                mfa_expires_at = clock_timestamp() + make_interval(secs => p_seconds)
             WHERE id = p_id AND consumed_at IS NULL AND user_id IS NOT NULL
            RETURNING host_tenant_id, email_sha256 INTO v_challenge;
            IF NOT FOUND THEN
                RETURN false;
            END IF;
            UPDATE public.sign_in_locks SET attempts = 0, window_until = NULL
             WHERE host_tenant_id = v_challenge.host_tenant_id
               AND email_sha256 = v_challenge.email_sha256;
            RETURN true;
        END $$
        """
    )
    # Every second-step guess is counted before it is compared, under row locks taken in one
    # order (the token's challenge, the firm's email row, the person's factor) so concurrent
    # guesses queue. The count is the factor's, across firms. 'ok' hands back the factor to check:
    # the enrolled one for `verify`, the pending one for `setup`. The guess over the limit locks
    # the factor and the firm's email for `p_lock_seconds`, and voids the token.
    op.execute(
        """
        CREATE FUNCTION portal_mfa_attempt(
            p_token_sha256 text, p_host text, p_kind text, p_max integer, p_lock_seconds integer
        ) RETURNS TABLE (outcome text, tenant_id uuid, user_id uuid, factor_ref text,
                         tries_left integer, locked_until timestamptz)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        #variable_conflict use_column
        DECLARE
            v_now timestamptz := clock_timestamp();
            v_challenge record;
            v_lock record;
            v_factor record;
            v_until timestamptz;
        BEGIN
            SELECT * INTO v_challenge FROM public.sign_in_challenges c
             WHERE c.mfa_token_sha256 = p_token_sha256 AND c.host = lower(p_host)
               AND c.mfa_kind = p_kind FOR UPDATE;
            IF NOT FOUND THEN
                RETURN QUERY SELECT 'unknown'::text, NULL::uuid, NULL::uuid, NULL::text, 0,
                    NULL::timestamptz;
                RETURN;
            END IF;
            INSERT INTO public.sign_in_locks (host_tenant_id, email_sha256)
            VALUES (v_challenge.host_tenant_id, v_challenge.email_sha256)
            ON CONFLICT DO NOTHING;
            SELECT * INTO v_lock FROM public.sign_in_locks l
             WHERE l.host_tenant_id = v_challenge.host_tenant_id
               AND l.email_sha256 = v_challenge.email_sha256 FOR UPDATE;
            SELECT * INTO v_factor FROM public.mfa_factors f
             WHERE f.user_id = v_challenge.user_id FOR UPDATE;
            v_until := greatest(
                CASE WHEN v_lock.locked_until > v_now THEN v_lock.locked_until END,
                CASE WHEN v_factor.mfa_locked_until > v_now THEN v_factor.mfa_locked_until END);
            IF v_until IS NOT NULL THEN
                RETURN QUERY SELECT 'locked'::text, NULL::uuid, NULL::uuid, NULL::text, 0,
                    v_until;
                RETURN;
            END IF;
            IF v_challenge.mfa_used_at IS NOT NULL OR v_challenge.mfa_expires_at <= v_now THEN
                RETURN QUERY SELECT 'unknown'::text, NULL::uuid, NULL::uuid, NULL::text, 0,
                    NULL::timestamptz;
                RETURN;
            END IF;
            IF v_factor.user_id IS NULL
               OR (p_kind = 'verify' AND v_factor.enrolled_at IS NULL)
               OR (p_kind = 'setup' AND (v_factor.enrolled_at IS NOT NULL
                                         OR v_challenge.mfa_setup_at IS NULL)) THEN
                RETURN QUERY SELECT 'unknown'::text, NULL::uuid, NULL::uuid, NULL::text, 0,
                    NULL::timestamptz;
                RETURN;
            END IF;
            IF v_factor.mfa_window_until IS NULL OR v_factor.mfa_window_until <= v_now THEN
                v_factor.mfa_attempts := 0;
                UPDATE public.mfa_factors SET mfa_attempts = 0,
                    mfa_window_until = v_now + make_interval(secs => p_lock_seconds)
                 WHERE mfa_factors.user_id = v_challenge.user_id;
            END IF;
            UPDATE public.mfa_factors SET mfa_attempts = mfa_attempts + 1
             WHERE mfa_factors.user_id = v_challenge.user_id;
            IF v_factor.mfa_attempts + 1 > p_max THEN
                v_until := v_now + make_interval(secs => p_lock_seconds);
                UPDATE public.mfa_factors SET mfa_locked_until = v_until
                 WHERE mfa_factors.user_id = v_challenge.user_id;
                UPDATE public.sign_in_locks SET locked_until = v_until
                 WHERE host_tenant_id = v_lock.host_tenant_id
                   AND email_sha256 = v_lock.email_sha256;
                UPDATE public.sign_in_challenges SET mfa_used_at = v_now
                 WHERE id = v_challenge.id;
                RETURN QUERY SELECT 'locked'::text, v_challenge.tenant_id, v_challenge.user_id,
                    NULL::text, 0, v_until;
                RETURN;
            END IF;
            RETURN QUERY SELECT 'ok'::text, v_challenge.tenant_id, v_challenge.user_id,
                v_factor.factor_ref, p_max - (v_factor.mfa_attempts + 1), NULL::timestamptz;
        END $$
        """
    )
    # A second-step guess missed: when it was the last one allowed (`p_tries_left` 0, from its
    # attempt), lock the factor and the firm's email (or keep the lock a later guess set) and void
    # the token. An earlier guess reports its own tries left. Rows are locked in
    # `portal_mfa_attempt`'s order.
    op.execute(
        """
        CREATE FUNCTION portal_mfa_missed(
            p_token_sha256 text, p_tries_left integer, p_lock_seconds integer
        ) RETURNS timestamptz
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        DECLARE
            v_challenge record;
            v_until timestamptz;
        BEGIN
            SELECT * INTO v_challenge FROM public.sign_in_challenges
             WHERE mfa_token_sha256 = p_token_sha256 FOR UPDATE;
            IF NOT FOUND OR p_tries_left > 0 THEN
                RETURN NULL;
            END IF;
            PERFORM 1 FROM public.sign_in_locks
             WHERE host_tenant_id = v_challenge.host_tenant_id
               AND email_sha256 = v_challenge.email_sha256 FOR UPDATE;
            UPDATE public.mfa_factors
               SET mfa_locked_until = CASE WHEN mfa_locked_until > clock_timestamp()
                   THEN mfa_locked_until
                   ELSE clock_timestamp() + make_interval(secs => p_lock_seconds) END
             WHERE user_id = v_challenge.user_id
            RETURNING mfa_locked_until INTO v_until;
            IF v_until IS NOT NULL THEN
                UPDATE public.sign_in_locks SET locked_until = greatest(locked_until, v_until)
                 WHERE host_tenant_id = v_challenge.host_tenant_id
                   AND email_sha256 = v_challenge.email_sha256;
                UPDATE public.sign_in_challenges SET mfa_used_at = clock_timestamp()
                 WHERE id = v_challenge.id AND mfa_used_at IS NULL;
            END IF;
            RETURN v_until;
        END $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION portal_mfa_backup_use(p_user_id uuid, p_code_sha256 text)
        RETURNS boolean
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            UPDATE public.mfa_backup_codes SET used_at = clock_timestamp()
             WHERE user_id = p_user_id AND code_sha256 = p_code_sha256 AND used_at IS NULL;
            RETURN FOUND;
        END $$
        """
    )
    # Setup is shown once per token, and only to a person without an enrolled factor.
    op.execute(
        """
        CREATE FUNCTION portal_mfa_setup_claim(p_token_sha256 text, p_host text)
        RETURNS TABLE (tenant_id uuid, user_id uuid)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        #variable_conflict use_column
        BEGIN
            RETURN QUERY
            UPDATE public.sign_in_challenges c SET mfa_setup_at = clock_timestamp()
             WHERE c.mfa_token_sha256 = p_token_sha256 AND c.host = lower(p_host)
               AND c.mfa_kind = 'setup' AND c.mfa_setup_at IS NULL AND c.mfa_used_at IS NULL
               AND c.mfa_expires_at > clock_timestamp()
               AND NOT EXISTS (SELECT 1 FROM public.mfa_factors f
                                WHERE f.user_id = c.user_id
                                  AND (f.enrolled_at IS NOT NULL
                                       OR f.mfa_locked_until > clock_timestamp()))
               AND NOT EXISTS (SELECT 1 FROM public.sign_in_locks l
                                WHERE l.host_tenant_id = c.host_tenant_id
                                  AND l.email_sha256 = c.email_sha256
                                  AND l.locked_until > clock_timestamp())
            RETURNING c.tenant_id, c.user_id;
        END $$
        """
    )
    # The factor setup made, waiting for its first code. Returns the pending factor it replaced
    # (for the caller to remove at the provider), or 'enrolled' when one is already enrolled.
    op.execute(
        """
        CREATE FUNCTION portal_mfa_factor_pending(
            p_user_id uuid, p_provider_user_ref text, p_factor_ref text
        ) RETURNS TABLE (outcome text, replaced text)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        DECLARE
            v_row record;
        BEGIN
            SELECT * INTO v_row FROM public.mfa_factors WHERE user_id = p_user_id FOR UPDATE;
            IF NOT FOUND THEN
                INSERT INTO public.mfa_factors (user_id, provider_user_ref, factor_ref)
                VALUES (p_user_id, p_provider_user_ref, p_factor_ref);
                RETURN QUERY SELECT 'ok'::text, NULL::text;
                RETURN;
            END IF;
            IF v_row.enrolled_at IS NOT NULL THEN
                RETURN QUERY SELECT 'enrolled'::text, NULL::text;
                RETURN;
            END IF;
            UPDATE public.mfa_factors SET provider_user_ref = p_provider_user_ref,
                factor_ref = p_factor_ref, created_at = clock_timestamp()
             WHERE user_id = p_user_id;
            RETURN QUERY SELECT 'ok'::text, v_row.factor_ref;
        END $$
        """
    )
    # The first code verified: the token is used, the pending factor enrolled and the backup
    # codes replaced, in one transaction. Nothing when the token or the factor moved on.
    op.execute(
        """
        CREATE FUNCTION portal_mfa_enrol(
            p_token_sha256 text, p_factor_ref text, p_codes text[]
        ) RETURNS TABLE (tenant_id uuid, user_id uuid)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        #variable_conflict use_column
        DECLARE
            v_challenge record;
        BEGIN
            IF cardinality(p_codes) <> 8 THEN
                RAISE EXCEPTION 'eight backup codes';
            END IF;
            UPDATE public.sign_in_challenges c SET mfa_used_at = clock_timestamp()
             WHERE c.mfa_token_sha256 = p_token_sha256 AND c.mfa_kind = 'setup'
               AND c.mfa_used_at IS NULL AND c.mfa_expires_at > clock_timestamp()
            RETURNING c.tenant_id, c.user_id INTO v_challenge;
            IF NOT FOUND THEN
                RETURN;
            END IF;
            UPDATE public.mfa_factors f SET enrolled_at = clock_timestamp(), mfa_attempts = 0,
                mfa_window_until = NULL
             WHERE f.user_id = v_challenge.user_id AND f.factor_ref = p_factor_ref
               AND f.enrolled_at IS NULL;
            IF NOT FOUND THEN
                RETURN;  -- a later setup replaced the pending factor: this token is spent
            END IF;
            DELETE FROM public.mfa_backup_codes b WHERE b.user_id = v_challenge.user_id;
            INSERT INTO public.mfa_backup_codes (user_id, code_sha256)
            SELECT v_challenge.user_id, unnest(p_codes);
            RETURN QUERY SELECT v_challenge.tenant_id, v_challenge.user_id;
        END $$
        """
    )
    # The second step verified: the token is used (once) and the guesses are cleared.
    op.execute(
        """
        CREATE FUNCTION portal_mfa_complete(p_token_sha256 text)
        RETURNS TABLE (tenant_id uuid, user_id uuid)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        #variable_conflict use_column
        DECLARE
            v_challenge record;
        BEGIN
            UPDATE public.sign_in_challenges c SET mfa_used_at = clock_timestamp()
             WHERE c.mfa_token_sha256 = p_token_sha256 AND c.mfa_kind = 'verify'
               AND c.mfa_used_at IS NULL AND c.mfa_expires_at > clock_timestamp()
            RETURNING c.tenant_id, c.user_id INTO v_challenge;
            IF NOT FOUND THEN
                RETURN;
            END IF;
            UPDATE public.mfa_factors SET mfa_attempts = 0, mfa_window_until = NULL
             WHERE mfa_factors.user_id = v_challenge.user_id;
            RETURN QUERY SELECT v_challenge.tenant_id, v_challenge.user_id;
        END $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION portal_mfa_enrolled(p_user_id uuid) RETURNS boolean
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
            SELECT EXISTS (SELECT 1 FROM public.mfa_factors
                            WHERE user_id = p_user_id AND enrolled_at IS NOT NULL)
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION portal_session_mark_mfa(p_session_id uuid, p_user_id uuid)
        RETURNS boolean
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            UPDATE public.auth_sessions SET mfa_at = clock_timestamp()
             WHERE id = p_session_id AND user_id = p_user_id AND surface = 'portal'
               AND ended_at IS NULL;
            RETURN FOUND;
        END $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION portal_device_trust(
            p_tenant_id uuid, p_user_id uuid, p_token_sha256 text, p_days integer,
            p_ua_family text
        ) RETURNS TABLE (device_id uuid, expires_at timestamptz)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        #variable_conflict use_column
        DECLARE
            v_now timestamptz := clock_timestamp();
        BEGIN
            IF p_days NOT BETWEEN 1 AND 30 THEN
                RAISE EXCEPTION 'a device is trusted for 1 to 30 days';
            END IF;
            RETURN QUERY
            INSERT INTO public.trusted_devices (tenant_id, user_id, token_sha256, created_at,
                expires_at, ua_family)
            VALUES (p_tenant_id, p_user_id, p_token_sha256, v_now,
                v_now + make_interval(days => p_days), p_ua_family)
            RETURNING trusted_devices.id, trusted_devices.expires_at;
        END $$
        """
    )
    # A device counts while it is unrevoked, unexpired and younger than the firm's current days
    # (a firm that shortens its days shortens the devices it already trusts).
    op.execute(
        """
        CREATE FUNCTION portal_device_check(
            p_tenant_id uuid, p_user_id uuid, p_token_sha256 text, p_days integer
        ) RETURNS timestamptz
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
            SELECT least(d.expires_at, d.created_at + make_interval(days => p_days))
              FROM public.trusted_devices d
             WHERE d.token_sha256 = p_token_sha256 AND d.tenant_id = p_tenant_id
               AND d.user_id = p_user_id AND d.revoked_at IS NULL
               AND d.expires_at > clock_timestamp()
               AND d.created_at + make_interval(days => p_days) > clock_timestamp()
        $$
        """
    )
    # `access.changed` for a person in a firm: their live portal sessions there end and their
    # trusted devices there are revoked. Returns what changed, for the audit.
    op.execute(
        """
        CREATE FUNCTION portal_access_revoke(p_tenant_id uuid, p_user_id uuid)
        RETURNS TABLE (kind text, id uuid)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        #variable_conflict use_column
        BEGIN
            RETURN QUERY
            WITH ended AS (
                UPDATE public.auth_sessions s SET ended_at = clock_timestamp(),
                    end_reason = 'revoked'
                 WHERE s.user_id = p_user_id AND s.tenant_id = p_tenant_id
                   AND s.surface = 'portal' AND s.ended_at IS NULL
                RETURNING s.id
            ), revoked AS (
                UPDATE public.trusted_devices d SET revoked_at = clock_timestamp(),
                    revoked_reason = 'access_changed'
                 WHERE d.user_id = p_user_id AND d.tenant_id = p_tenant_id
                   AND d.revoked_at IS NULL
                RETURNING d.id
            )
            SELECT 'session'::text, ended.id FROM ended
            UNION ALL SELECT 'device'::text, revoked.id FROM revoked;
        END $$
        """
    )
    for function in _FUNCTIONS:
        op.execute(f"REVOKE ALL ON FUNCTION {function} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {function} TO abacus_app")


def downgrade() -> None:
    for function in reversed(_FUNCTIONS):
        op.execute(f"DROP FUNCTION {function}")
    op.execute("ALTER TABLE sign_in_challenges DROP CONSTRAINT sign_in_challenges_mfa")
    op.execute(
        "ALTER TABLE sign_in_challenges DROP COLUMN mfa_used_at, DROP COLUMN mfa_setup_at, "
        "DROP COLUMN mfa_expires_at, DROP COLUMN mfa_kind, DROP COLUMN mfa_token_sha256"
    )
    op.execute("DROP TABLE portal_security_policies")
    op.execute("DROP TABLE trusted_devices")
    op.execute("DROP TABLE mfa_backup_codes")
    op.execute("DROP TABLE mfa_factors")
