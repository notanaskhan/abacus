"""Staff sessions behind the BFF (P-01-T09; ADR-141, ADR-165; DEC-140).

Three global tables, with no app or identity-role privileges, reached only through
SECURITY DEFINER functions. A session spans memberships, so it belongs to no tenant.

- `auth_login_states`: one sign-in attempt's PKCE verifier and safe return path, keyed by the
  SHA-256 of its `state`. Single use, valid 10 minutes.
- `auth_sessions`: a person's session. It holds:
  - the provider's sealed refresh token (platform key) and when they last did MFA;
  - the idle and absolute expiries (DEC-140: 30 minutes idle, 12 hours absolute);
  - how it ended.
- `auth_session_cookies`: every refresh-cookie value ever issued, as a SHA-256. Rotation retires
  the presented value and issues the next one. Presenting a retired value is reuse: the whole
  session ends `reuse_detected` (AC 5.1.4).

Definers:
- `auth_state_put` and `auth_state_take`;
- `auth_session_start`;
- `auth_session_rotate`, which answers `ok`, `unknown`, `ended`, `reused`, or `idle` or
  `absolute` when it has just ended the session for a timeout;
- `auth_session_set_refresh`, and `auth_session_revoke` for when the provider refuses a refresh;
- `auth_session_end`, which ends only the signed-in person's own session.

Revision ID: 0101
Revises: 0100
"""

from __future__ import annotations

from alembic import op

revision = "0101"
down_revision = "0100"
branch_labels = None
depends_on = None

_FUNCTIONS = (
    "auth_state_put(text, text, text)",
    "auth_state_take(text)",
    "auth_session_start(uuid, text, bytea, timestamptz, text, integer, integer)",
    "auth_session_rotate(text, text, integer)",
    "auth_session_set_refresh(uuid, bytea)",
    "auth_session_revoke(uuid)",
    "auth_session_end(text, text, uuid)",
)


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE auth_login_states (
            state_sha256 text PRIMARY KEY CHECK (state_sha256 ~ '^[0-9a-f]{64}$'),
            code_verifier text NOT NULL CHECK (code_verifier ~ '^[A-Za-z0-9._~-]{43,128}$'),
            return_to text NOT NULL CHECK (return_to ~ '^/[^/\\\\]' OR return_to = '/'),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            expires_at timestamptz NOT NULL DEFAULT clock_timestamp() + interval '10 minutes'
        )
        """
    )
    op.execute(
        """
        CREATE TABLE auth_sessions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id uuid NOT NULL REFERENCES users (id),
            provider text NOT NULL CHECK (provider IN ('workos', 'oidc')),
            provider_refresh_enc bytea NULL CHECK (octet_length(provider_refresh_enc) <= 8192),
            mfa_at timestamptz NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            last_seen_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            idle_expires_at timestamptz NOT NULL,
            absolute_expires_at timestamptz NOT NULL,
            ended_at timestamptz NULL,
            end_reason text NULL CHECK (end_reason IN ('sign_out', 'idle', 'absolute',
                'reuse_detected', 'revoked', 'membership_removed')),
            CHECK ((ended_at IS NULL) = (end_reason IS NULL))
        )
        """
    )
    op.execute("CREATE INDEX auth_sessions_live ON auth_sessions (user_id) WHERE ended_at IS NULL")
    op.execute(
        """
        CREATE TABLE auth_session_cookies (
            cookie_sha256 text PRIMARY KEY CHECK (cookie_sha256 ~ '^[0-9a-f]{64}$'),
            session_id uuid NOT NULL REFERENCES auth_sessions (id),
            issued_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            retired_at timestamptz NULL
        )
        """
    )
    for table in ("auth_login_states", "auth_sessions", "auth_session_cookies"):
        op.execute(f"REVOKE ALL ON {table} FROM PUBLIC, abacus_app")

    op.execute(
        """
        CREATE FUNCTION auth_state_put(p_state_sha256 text, p_verifier text, p_return_to text)
        RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            DELETE FROM public.auth_login_states WHERE expires_at < clock_timestamp();
            INSERT INTO public.auth_login_states (state_sha256, code_verifier, return_to)
            VALUES (p_state_sha256, p_verifier, p_return_to);
        END $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION auth_state_take(p_state_sha256 text)
        RETURNS TABLE (code_verifier text, return_to text)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            RETURN QUERY
            DELETE FROM public.auth_login_states s
             WHERE s.state_sha256 = p_state_sha256 AND s.expires_at >= clock_timestamp()
            RETURNING s.code_verifier, s.return_to;
        END $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION auth_session_start(
            p_user_id uuid, p_provider text, p_refresh bytea, p_mfa_at timestamptz,
            p_cookie_sha256 text, p_idle_seconds integer, p_absolute_seconds integer
        ) RETURNS uuid
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        DECLARE
            v_id uuid;
        BEGIN
            INSERT INTO public.auth_sessions (user_id, provider, provider_refresh_enc, mfa_at,
                idle_expires_at, absolute_expires_at)
            VALUES (p_user_id, p_provider, p_refresh, p_mfa_at,
                clock_timestamp() + make_interval(secs => p_idle_seconds),
                clock_timestamp() + make_interval(secs => p_absolute_seconds))
            RETURNING id INTO v_id;
            INSERT INTO public.auth_session_cookies (cookie_sha256, session_id)
            VALUES (p_cookie_sha256, v_id);
            RETURN v_id;
        END $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION auth_session_rotate(
            p_cookie_sha256 text, p_new_cookie_sha256 text, p_idle_seconds integer
        ) RETURNS TABLE (outcome text, session_id uuid, user_id uuid, provider_refresh_enc bytea,
                         mfa_at timestamptz)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        #variable_conflict use_column
        DECLARE
            v_cookie record;
            v_session record;
            v_now timestamptz := clock_timestamp();
            v_reason text;
        BEGIN
            SELECT c.session_id, c.retired_at INTO v_cookie
              FROM public.auth_session_cookies c WHERE c.cookie_sha256 = p_cookie_sha256;
            IF NOT FOUND THEN
                RETURN QUERY SELECT 'unknown'::text, NULL::uuid, NULL::uuid, NULL::bytea,
                    NULL::timestamptz;
                RETURN;
            END IF;
            SELECT * INTO v_session FROM public.auth_sessions s
             WHERE s.id = v_cookie.session_id FOR UPDATE;
            IF v_session.ended_at IS NOT NULL THEN
                RETURN QUERY SELECT 'ended'::text, v_session.id, v_session.user_id,
                    NULL::bytea, NULL::timestamptz;
                RETURN;
            END IF;
            IF v_cookie.retired_at IS NOT NULL THEN
                UPDATE public.auth_sessions SET ended_at = v_now, end_reason = 'reuse_detected'
                 WHERE id = v_session.id;
                RETURN QUERY SELECT 'reused'::text, v_session.id, v_session.user_id,
                    NULL::bytea, NULL::timestamptz;
                RETURN;
            END IF;
            IF v_now >= v_session.absolute_expires_at OR v_now >= v_session.idle_expires_at THEN
                v_reason := CASE WHEN v_now >= v_session.absolute_expires_at
                                 THEN 'absolute' ELSE 'idle' END;
                UPDATE public.auth_sessions SET ended_at = v_now, end_reason = v_reason
                 WHERE id = v_session.id;
                RETURN QUERY SELECT v_reason, v_session.id, v_session.user_id,
                    NULL::bytea, NULL::timestamptz;
                RETURN;
            END IF;
            UPDATE public.auth_session_cookies SET retired_at = v_now
             WHERE cookie_sha256 = p_cookie_sha256;
            INSERT INTO public.auth_session_cookies (cookie_sha256, session_id)
            VALUES (p_new_cookie_sha256, v_session.id);
            UPDATE public.auth_sessions SET last_seen_at = v_now,
                idle_expires_at = least(v_now + make_interval(secs => p_idle_seconds),
                                        v_session.absolute_expires_at)
             WHERE id = v_session.id;
            RETURN QUERY SELECT 'ok'::text, v_session.id, v_session.user_id,
                v_session.provider_refresh_enc, v_session.mfa_at;
        END $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION auth_session_set_refresh(p_session_id uuid, p_refresh bytea)
        RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            UPDATE public.auth_sessions SET provider_refresh_enc = p_refresh
             WHERE id = p_session_id AND ended_at IS NULL;
        END $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION auth_session_revoke(p_session_id uuid)
        RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            UPDATE public.auth_sessions SET ended_at = clock_timestamp(), end_reason = 'revoked'
             WHERE id = p_session_id AND ended_at IS NULL;
        END $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION auth_session_end(p_cookie_sha256 text, p_reason text, p_user_id uuid)
        RETURNS TABLE (session_id uuid, user_id uuid, provider_refresh_enc bytea)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        #variable_conflict use_column
        BEGIN
            RETURN QUERY
            UPDATE public.auth_sessions s SET ended_at = clock_timestamp(), end_reason = p_reason
              FROM public.auth_session_cookies c
             WHERE c.cookie_sha256 = p_cookie_sha256 AND s.id = c.session_id
               AND s.user_id = p_user_id AND s.ended_at IS NULL
            RETURNING s.id, s.user_id, s.provider_refresh_enc;
        END $$
        """
    )
    for function in _FUNCTIONS:
        op.execute(f"REVOKE ALL ON FUNCTION {function} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {function} TO abacus_app")


def downgrade() -> None:
    for function in reversed(_FUNCTIONS):
        op.execute(f"DROP FUNCTION {function}")
    op.execute("DROP TABLE auth_session_cookies")
    op.execute("DROP TABLE auth_sessions")
    op.execute("DROP TABLE auth_login_states")
