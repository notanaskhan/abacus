"""DEC-535 follow-up (P-08; DEC-583): a portal session's idle clock moves only on the person's own
activity, as a staff session's does since G-02-T14 (security review M3).

`portal_session_rotate` gains `p_active`. The portal SPA marks a refresh `X-Abacus-Activity: user`
only after keyboard or pointer input since its last refresh (or on a page load); the route passes
that mark. An unmarked refresh (a background poll) still rotates the cookie and mints a token, but
leaves `last_seen_at` and `idle_expires_at` as they were, and the new token never outlives the idle
expiry. The six-argument function is dropped; the downgrade restores 0116's.

Revision ID: 0225
Revises: 0244
"""

from __future__ import annotations

from alembic import op

revision = "0225"
down_revision = "0244"
branch_labels = None
depends_on = None

_OLD = "portal_session_rotate(text, text, text, text, integer, integer)"
_NEW = "portal_session_rotate(text, text, text, text, integer, integer, boolean)"

_NEW_FUNCTION = """
        CREATE FUNCTION portal_session_rotate(
            p_cookie_sha256 text, p_new_cookie_sha256 text, p_host text, p_access_sha256 text,
            p_access_seconds integer, p_idle_seconds integer, p_active boolean
        ) RETURNS TABLE (outcome text, session_id uuid, user_id uuid, tenant_id uuid)
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
                RETURN QUERY SELECT 'unknown'::text, NULL::uuid, NULL::uuid, NULL::uuid;
                RETURN;
            END IF;
            SELECT * INTO v_session FROM public.auth_sessions s
             WHERE s.id = v_cookie.session_id FOR UPDATE;
            -- Another host's or a staff session's cookie is no session here (ADR-168 §3).
            IF v_session.surface <> 'portal' OR v_session.host <> lower(p_host) THEN
                RETURN QUERY SELECT 'unknown'::text, NULL::uuid, NULL::uuid, NULL::uuid;
                RETURN;
            END IF;
            IF v_session.ended_at IS NOT NULL THEN
                RETURN QUERY SELECT 'ended'::text, v_session.id, v_session.user_id,
                    v_session.tenant_id;
                RETURN;
            END IF;
            IF v_cookie.retired_at IS NOT NULL THEN
                UPDATE public.auth_sessions SET ended_at = v_now, end_reason = 'reuse_detected'
                 WHERE id = v_session.id;
                RETURN QUERY SELECT 'reused'::text, v_session.id, v_session.user_id,
                    v_session.tenant_id;
                RETURN;
            END IF;
            IF v_now >= v_session.absolute_expires_at OR v_now >= v_session.idle_expires_at THEN
                v_reason := CASE WHEN v_now >= v_session.absolute_expires_at
                                 THEN 'absolute' ELSE 'idle' END;
                UPDATE public.auth_sessions SET ended_at = v_now, end_reason = v_reason
                 WHERE id = v_session.id;
                RETURN QUERY SELECT v_reason, v_session.id, v_session.user_id,
                    v_session.tenant_id;
                RETURN;
            END IF;
            UPDATE public.auth_session_cookies SET retired_at = v_now
             WHERE cookie_sha256 = p_cookie_sha256;
            INSERT INTO public.auth_session_cookies (cookie_sha256, session_id)
            VALUES (p_new_cookie_sha256, v_session.id);
            -- DEC-583: only the person's own activity moves the idle clock; a background poll's
            -- refresh rotates the cookie and the token and leaves `last_seen_at` and the idle
            -- expiry where they were.
            UPDATE public.auth_sessions SET
                last_seen_at = CASE WHEN p_active THEN v_now ELSE last_seen_at END,
                access_sha256 = p_access_sha256,
                access_expires_at = least(v_now + make_interval(secs => p_access_seconds),
                                          v_session.absolute_expires_at,
                                          CASE WHEN p_active THEN v_session.absolute_expires_at
                                               ELSE v_session.idle_expires_at END),
                idle_expires_at = CASE WHEN p_active
                    THEN least(v_now + make_interval(secs => p_idle_seconds),
                               v_session.absolute_expires_at)
                    ELSE v_session.idle_expires_at END
             WHERE id = v_session.id;
            RETURN QUERY SELECT 'ok'::text, v_session.id, v_session.user_id,
                v_session.tenant_id;
        END $$
"""

_OLD_FUNCTION = """
        CREATE FUNCTION portal_session_rotate(
            p_cookie_sha256 text, p_new_cookie_sha256 text, p_host text, p_access_sha256 text,
            p_access_seconds integer, p_idle_seconds integer
        ) RETURNS TABLE (outcome text, session_id uuid, user_id uuid, tenant_id uuid)
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
                RETURN QUERY SELECT 'unknown'::text, NULL::uuid, NULL::uuid, NULL::uuid;
                RETURN;
            END IF;
            SELECT * INTO v_session FROM public.auth_sessions s
             WHERE s.id = v_cookie.session_id FOR UPDATE;
            -- Another host's or a staff session's cookie is no session here (ADR-168 §3).
            IF v_session.surface <> 'portal' OR v_session.host <> lower(p_host) THEN
                RETURN QUERY SELECT 'unknown'::text, NULL::uuid, NULL::uuid, NULL::uuid;
                RETURN;
            END IF;
            IF v_session.ended_at IS NOT NULL THEN
                RETURN QUERY SELECT 'ended'::text, v_session.id, v_session.user_id,
                    v_session.tenant_id;
                RETURN;
            END IF;
            IF v_cookie.retired_at IS NOT NULL THEN
                UPDATE public.auth_sessions SET ended_at = v_now, end_reason = 'reuse_detected'
                 WHERE id = v_session.id;
                RETURN QUERY SELECT 'reused'::text, v_session.id, v_session.user_id,
                    v_session.tenant_id;
                RETURN;
            END IF;
            IF v_now >= v_session.absolute_expires_at OR v_now >= v_session.idle_expires_at THEN
                v_reason := CASE WHEN v_now >= v_session.absolute_expires_at
                                 THEN 'absolute' ELSE 'idle' END;
                UPDATE public.auth_sessions SET ended_at = v_now, end_reason = v_reason
                 WHERE id = v_session.id;
                RETURN QUERY SELECT v_reason, v_session.id, v_session.user_id,
                    v_session.tenant_id;
                RETURN;
            END IF;
            UPDATE public.auth_session_cookies SET retired_at = v_now
             WHERE cookie_sha256 = p_cookie_sha256;
            INSERT INTO public.auth_session_cookies (cookie_sha256, session_id)
            VALUES (p_new_cookie_sha256, v_session.id);
            UPDATE public.auth_sessions SET last_seen_at = v_now,
                access_sha256 = p_access_sha256,
                access_expires_at = least(v_now + make_interval(secs => p_access_seconds),
                                          v_session.absolute_expires_at),
                idle_expires_at = least(v_now + make_interval(secs => p_idle_seconds),
                                        v_session.absolute_expires_at)
             WHERE id = v_session.id;
            RETURN QUERY SELECT 'ok'::text, v_session.id, v_session.user_id,
                v_session.tenant_id;
        END $$
"""


def _grant(signature: str) -> None:
    op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO abacus_app")


def upgrade() -> None:
    op.execute(f"DROP FUNCTION {_OLD}")
    op.execute(_NEW_FUNCTION)
    _grant(_NEW)


def downgrade() -> None:
    op.execute(f"DROP FUNCTION {_NEW}")
    op.execute(_OLD_FUNCTION)
    _grant(_OLD)
