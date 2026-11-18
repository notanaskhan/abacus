"""Platform staff sessions behind the console BFF (G-04-T14; TASK-8548; DEC-5532; ADR-165).

Accrued platform staff sign in on the staff issuer and are never firm members (ADR-028), so their
console sessions belong to no tenant and no `users` row: two global tables, with no app privileges,
reached only through SECURITY DEFINER functions, shaped like 0101's.

- `platform_staff_sessions`: a staff member's console session — the staff issuer and subject, the
  provider's sealed refresh token (platform key), when they last did MFA, the idle and absolute
  expiries (DEC-140: 30 minutes idle, 12 hours absolute) and how it ended.
- `platform_staff_session_cookies`: every refresh-cookie value ever issued, as a SHA-256. Rotation
  retires the presented value and issues the next; a retired value presented again is reuse and
  ends the whole session `reuse_detected`.

The sign-in attempt's state and PKCE verifier reuse 0101's `auth_login_states` through
`auth_state_put` and `auth_state_take`.

Definers: `platform_staff_session_start`; `platform_staff_session_rotate`, answering `ok`,
`unknown`, `ended`, `reused`, or `idle` / `absolute` when it has just ended the session;
`platform_staff_session_set_refresh`; `platform_staff_session_revoke`; and
`platform_staff_session_end`, which ends only the session behind the presented cookie.

Revision ID: 0969
Revises: 0968
"""

from __future__ import annotations

from alembic import op

revision = "0969"
down_revision = "0968"
branch_labels = None
depends_on = None

_FUNCTIONS = (
    "platform_staff_session_start(text, text, bytea, timestamptz, text, integer, integer)",
    "platform_staff_session_rotate(text, text, integer, boolean)",
    "platform_staff_session_set_refresh(uuid, bytea)",
    "platform_staff_session_revoke(uuid)",
    "platform_staff_session_end(text, text)",
)


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE platform_staff_sessions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            staff_issuer text NOT NULL CHECK (length(staff_issuer) BETWEEN 1 AND 500),
            staff_subject text NOT NULL CHECK (length(staff_subject) BETWEEN 1 AND 255),
            provider_refresh_enc bytea NULL CHECK (octet_length(provider_refresh_enc) <= 8192),
            mfa_at timestamptz NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            last_seen_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            idle_expires_at timestamptz NOT NULL,
            absolute_expires_at timestamptz NOT NULL,
            ended_at timestamptz NULL,
            end_reason text NULL CHECK (end_reason IN ('sign_out', 'idle', 'absolute',
                'reuse_detected', 'revoked')),
            CHECK ((ended_at IS NULL) = (end_reason IS NULL))
        )
        """
    )
    op.execute(
        "CREATE INDEX platform_staff_sessions_live ON platform_staff_sessions "
        "(staff_issuer, staff_subject) WHERE ended_at IS NULL"
    )
    op.execute(
        """
        CREATE TABLE platform_staff_session_cookies (
            cookie_sha256 text PRIMARY KEY CHECK (cookie_sha256 ~ '^[0-9a-f]{64}$'),
            session_id uuid NOT NULL REFERENCES platform_staff_sessions (id),
            issued_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            retired_at timestamptz NULL
        )
        """
    )
    for table in ("platform_staff_sessions", "platform_staff_session_cookies"):
        op.execute(f"REVOKE ALL ON {table} FROM PUBLIC, abacus_app")

    op.execute(
        """
        CREATE FUNCTION platform_staff_session_start(
            p_issuer text, p_subject text, p_refresh bytea, p_mfa_at timestamptz,
            p_cookie_sha256 text, p_idle_seconds integer, p_absolute_seconds integer
        ) RETURNS uuid
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        DECLARE
            v_id uuid;
        BEGIN
            INSERT INTO public.platform_staff_sessions (staff_issuer, staff_subject,
                provider_refresh_enc, mfa_at, idle_expires_at, absolute_expires_at)
            VALUES (p_issuer, p_subject, p_refresh, p_mfa_at,
                clock_timestamp() + make_interval(secs => p_idle_seconds),
                clock_timestamp() + make_interval(secs => p_absolute_seconds))
            RETURNING id INTO v_id;
            INSERT INTO public.platform_staff_session_cookies (cookie_sha256, session_id)
            VALUES (p_cookie_sha256, v_id);
            RETURN v_id;
        END $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION platform_staff_session_rotate(
            p_cookie_sha256 text, p_new_cookie_sha256 text, p_idle_seconds integer,
            p_active boolean
        ) RETURNS TABLE (outcome text, session_id uuid, staff_issuer text, staff_subject text,
                         provider_refresh_enc bytea)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        #variable_conflict use_column
        DECLARE
            v_cookie record;
            v_session record;
            v_now timestamptz := clock_timestamp();
            v_reason text;
        BEGIN
            SELECT c.session_id, c.retired_at INTO v_cookie
              FROM public.platform_staff_session_cookies c
             WHERE c.cookie_sha256 = p_cookie_sha256;
            IF NOT FOUND THEN
                RETURN QUERY SELECT 'unknown'::text, NULL::uuid, NULL::text, NULL::text,
                    NULL::bytea;
                RETURN;
            END IF;
            SELECT * INTO v_session FROM public.platform_staff_sessions s
             WHERE s.id = v_cookie.session_id FOR UPDATE;
            IF v_session.ended_at IS NOT NULL THEN
                RETURN QUERY SELECT 'ended'::text, v_session.id, v_session.staff_issuer,
                    v_session.staff_subject, NULL::bytea;
                RETURN;
            END IF;
            IF v_cookie.retired_at IS NOT NULL THEN
                UPDATE public.platform_staff_sessions
                   SET ended_at = v_now, end_reason = 'reuse_detected'
                 WHERE id = v_session.id;
                RETURN QUERY SELECT 'reused'::text, v_session.id, v_session.staff_issuer,
                    v_session.staff_subject, NULL::bytea;
                RETURN;
            END IF;
            IF v_now >= v_session.absolute_expires_at OR v_now >= v_session.idle_expires_at THEN
                v_reason := CASE WHEN v_now >= v_session.absolute_expires_at
                                 THEN 'absolute' ELSE 'idle' END;
                UPDATE public.platform_staff_sessions SET ended_at = v_now, end_reason = v_reason
                 WHERE id = v_session.id;
                RETURN QUERY SELECT v_reason, v_session.id, v_session.staff_issuer,
                    v_session.staff_subject, NULL::bytea;
                RETURN;
            END IF;
            UPDATE public.platform_staff_session_cookies SET retired_at = v_now
             WHERE cookie_sha256 = p_cookie_sha256;
            INSERT INTO public.platform_staff_session_cookies (cookie_sha256, session_id)
            VALUES (p_new_cookie_sha256, v_session.id);
            -- Only the person's own activity moves the idle clock (as 0220, security review M3): a
            -- refresh a background poll caused keeps the last activity where it was.
            IF p_active THEN
                UPDATE public.platform_staff_sessions SET last_seen_at = v_now,
                    idle_expires_at = least(v_now + make_interval(secs => p_idle_seconds),
                                            v_session.absolute_expires_at)
                 WHERE id = v_session.id;
            END IF;
            RETURN QUERY SELECT 'ok'::text, v_session.id, v_session.staff_issuer,
                v_session.staff_subject, v_session.provider_refresh_enc;
        END $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION platform_staff_session_set_refresh(p_session_id uuid, p_refresh bytea)
        RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            UPDATE public.platform_staff_sessions SET provider_refresh_enc = p_refresh
             WHERE id = p_session_id AND ended_at IS NULL;
        END $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION platform_staff_session_revoke(p_session_id uuid)
        RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            UPDATE public.platform_staff_sessions
               SET ended_at = clock_timestamp(), end_reason = 'revoked'
             WHERE id = p_session_id AND ended_at IS NULL;
        END $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION platform_staff_session_end(p_cookie_sha256 text, p_reason text)
        RETURNS TABLE (session_id uuid, staff_issuer text, staff_subject text,
                       provider_refresh_enc bytea)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        #variable_conflict use_column
        BEGIN
            IF p_reason NOT IN ('sign_out', 'revoked') THEN
                RAISE EXCEPTION 'platform_staff_session_end_reason'
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN QUERY
            UPDATE public.platform_staff_sessions s
               SET ended_at = clock_timestamp(), end_reason = p_reason
              FROM public.platform_staff_session_cookies c
             WHERE c.cookie_sha256 = p_cookie_sha256 AND c.retired_at IS NULL
               AND s.id = c.session_id AND s.ended_at IS NULL
            RETURNING s.id, s.staff_issuer, s.staff_subject, s.provider_refresh_enc;
        END $$
        """
    )
    for function in _FUNCTIONS:
        op.execute(f"REVOKE ALL ON FUNCTION {function} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {function} TO abacus_app")


def downgrade() -> None:
    for function in reversed(_FUNCTIONS):
        op.execute(f"DROP FUNCTION {function}")
    op.execute("DROP TABLE platform_staff_session_cookies")
    op.execute("DROP TABLE platform_staff_sessions")
