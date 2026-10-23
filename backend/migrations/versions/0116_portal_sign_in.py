"""P-08-T10: portal sign-in by emailed code, and portal sessions (ADR-168; DEC-155; SPEC-320).

Two new global tables, with no app or identity-role privileges, reached only through SECURITY
DEFINER functions (as 0101's staff sessions are). Before sign-in there is no tenant: the host
names the firm inside the definers, and no tenant id is ever returned to the person signing in.

- `sign_in_challenges`: one sign-in attempt on one of a firm's active portal hosts for one email
  (kept as a SHA-256 of the case-folded address). The person is set only when the email belongs
  to an active client of that firm with a grant; otherwise it is null and no code is sent, but
  the row behaves the same (no oracle). A host no firm has active writes nothing. The code is
  issued at delivery, so only its salted digest is kept; a resend replaces it. Codes live 10
  minutes.
- `sign_in_locks`: per firm and email, the guesses in the current 15-minute window over every
  challenge, and the 15-minute lock after the third wrong one. Each guess is counted before it is
  compared (`portal_sign_in_attempt`), so neither parallel requests nor fresh challenges get more.

`auth_sessions` gains the portal surface: `surface`, the `tenant_id` and `host` it was minted on,
and the opaque access token's SHA-256 and expiry (15 minutes). A portal session is resolved only
on its own host (ADR-168 §3).

Definers: `portal_sign_in_start`, `portal_sign_in_issue` (the code's digest, at delivery),
`portal_sign_in_attempt`, `portal_sign_in_missed`, `portal_sign_in_consume`,
`portal_sign_in_resend`, `portal_session_start`, `portal_session_resolve`, `portal_session_rotate`
and `portal_session_end_id`. Sign-out also uses `auth_session_end` for the cookie.

Revision ID: 0116
Revises: 0115
"""

from __future__ import annotations

from alembic import op

revision = "0116"
down_revision = "0115"
branch_labels = None
depends_on = None

_FUNCTIONS = (
    "portal_sign_in_start(text, text, integer, integer)",
    "portal_sign_in_issue(uuid, bytea, bytea)",
    "portal_sign_in_attempt(uuid, text, integer, integer)",
    "portal_sign_in_missed(uuid, integer, integer)",
    "portal_sign_in_consume(uuid)",
    "portal_sign_in_resend(uuid, text, integer, integer)",
    "portal_session_start(uuid, uuid, text, text, integer, text, integer, integer)",
    "portal_session_resolve(text, text)",
    "portal_session_rotate(text, text, text, text, integer, integer)",
    "portal_session_end_id(uuid, uuid)",
)


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE sign_in_challenges (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            host text NOT NULL CHECK (length(host) BETWEEN 1 AND 253),
            host_tenant_id uuid NOT NULL REFERENCES firms (tenant_id),
            email_sha256 text NOT NULL CHECK (email_sha256 ~ '^[0-9a-f]{64}$'),
            tenant_id uuid NULL REFERENCES firms (tenant_id),
            user_id uuid NULL REFERENCES users (id),
            code_salt bytea NULL CHECK (octet_length(code_salt) = 16),
            code_digest bytea NULL CHECK (octet_length(code_digest) = 32),
            code_expires_at timestamptz NOT NULL,
            resend_available_at timestamptz NOT NULL,
            attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            consumed_at timestamptz NULL,
            CHECK ((tenant_id IS NULL) = (user_id IS NULL)),
            CHECK (tenant_id IS NULL OR tenant_id = host_tenant_id),
            CHECK ((code_salt IS NULL) = (code_digest IS NULL))
        )
        """
    )
    op.execute(
        "CREATE INDEX sign_in_challenges_email "
        "ON sign_in_challenges (host_tenant_id, email_sha256, created_at)"
    )
    # One row per firm and email: the attempts in the current 15-minute window, and the lock.
    # Every challenge for the email on any of the firm's hosts counts against the same row.
    op.execute(
        """
        CREATE TABLE sign_in_locks (
            host_tenant_id uuid NOT NULL REFERENCES firms (tenant_id),
            email_sha256 text NOT NULL CHECK (email_sha256 ~ '^[0-9a-f]{64}$'),
            attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
            window_until timestamptz NULL,
            locked_until timestamptz NULL,
            PRIMARY KEY (host_tenant_id, email_sha256)
        )
        """
    )
    for table in ("sign_in_challenges", "sign_in_locks"):
        op.execute(f"REVOKE ALL ON {table} FROM PUBLIC, abacus_app")

    op.execute("ALTER TABLE auth_sessions DROP CONSTRAINT auth_sessions_provider_check")
    op.execute(
        "ALTER TABLE auth_sessions ADD CONSTRAINT auth_sessions_provider_check "
        "CHECK (provider IN ('workos', 'oidc', 'portal_code'))"
    )
    op.execute(
        """
        ALTER TABLE auth_sessions
            ADD COLUMN surface text NOT NULL DEFAULT 'staff'
                CHECK (surface IN ('staff', 'portal')),
            ADD COLUMN tenant_id uuid NULL REFERENCES firms (tenant_id),
            ADD COLUMN host text NULL CHECK (length(host) BETWEEN 1 AND 253),
            ADD COLUMN access_sha256 text NULL UNIQUE CHECK (access_sha256 ~ '^[0-9a-f]{64}$'),
            ADD COLUMN access_expires_at timestamptz NULL,
            ADD CONSTRAINT auth_sessions_portal_pinned CHECK (
                (surface = 'staff' AND tenant_id IS NULL AND host IS NULL
                    AND access_sha256 IS NULL)
                OR (surface = 'portal' AND tenant_id IS NOT NULL AND host IS NOT NULL
                    AND provider = 'portal_code')
            )
        """
    )

    # The host's firm and the eligible client person, read under that firm's tenant setting and
    # restored after (0111's pattern). Eligible: an active client membership and an active,
    # unexpired grant in that firm. A host no firm has active writes nothing: it gets a fresh id
    # that no later call knows. `send` is false when the person is unknown, locked out, or was
    # sent a code for this firm in the last `p_resend_seconds` (no mail bombing through start).
    op.execute(
        """
        CREATE FUNCTION portal_sign_in_start(
            p_host text, p_email text, p_code_seconds integer, p_resend_seconds integer
        ) RETURNS TABLE (challenge_id uuid, code_expires_at timestamptz,
                         resend_available_at timestamptz, tenant_id uuid, user_id uuid,
                         send boolean)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        #variable_conflict use_column
        DECLARE
            v_now timestamptz := clock_timestamp();
            v_previous text := current_setting('app.tenant_id', true);
            v_email_sha text := encode(sha256(convert_to(lower(trim(p_email)), 'UTF8')), 'hex');
            v_host text := lower(p_host);
            v_firm uuid;
            v_user uuid;
            v_held boolean;
            v_id uuid;
        BEGIN
            SELECT d.tenant_id INTO v_firm FROM public.portal_domains d
             WHERE d.hostname = v_host AND d.status = 'active';
            IF v_firm IS NULL THEN
                RETURN QUERY SELECT gen_random_uuid(),
                    v_now + make_interval(secs => p_code_seconds),
                    v_now + make_interval(secs => p_resend_seconds),
                    NULL::uuid, NULL::uuid, false;
                RETURN;
            END IF;
            PERFORM set_config('app.tenant_id', v_firm::text, true);
            SELECT u.id INTO v_user FROM public.users u
              JOIN public.memberships m ON m.user_id = u.id AND m.tenant_id = v_firm
             WHERE lower(u.email) = lower(trim(p_email)) AND m.kind = 'client'
               AND m.status = 'active'
               AND EXISTS (
                   SELECT 1 FROM public.client_access_grants g
                    WHERE g.tenant_id = v_firm AND g.user_id = u.id
                      AND g.status = 'active'
                      AND (g.expires_at IS NULL OR g.expires_at > v_now))
             LIMIT 1;
            PERFORM set_config('app.tenant_id', coalesce(v_previous, ''), true);
            SELECT EXISTS (SELECT 1 FROM public.sign_in_locks l
                            WHERE l.host_tenant_id = v_firm AND l.email_sha256 = v_email_sha
                              AND l.locked_until > v_now)
                OR EXISTS (SELECT 1 FROM public.sign_in_challenges c
                            WHERE c.host_tenant_id = v_firm AND c.email_sha256 = v_email_sha
                              AND c.user_id IS NOT NULL
                              AND c.created_at > v_now - make_interval(secs => p_resend_seconds))
              INTO v_held;
            INSERT INTO public.sign_in_challenges (host, host_tenant_id, email_sha256, tenant_id,
                user_id, code_expires_at, resend_available_at)
            VALUES (v_host, v_firm, v_email_sha, CASE WHEN v_user IS NOT NULL THEN v_firm END,
                v_user, v_now + make_interval(secs => p_code_seconds),
                v_now + make_interval(secs => p_resend_seconds))
            RETURNING id INTO v_id;
            RETURN QUERY SELECT c.id, c.code_expires_at, c.resend_available_at, c.tenant_id,
                c.user_id, c.user_id IS NOT NULL AND NOT v_held
              FROM public.sign_in_challenges c WHERE c.id = v_id;
        END $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION portal_sign_in_issue(p_id uuid, p_salt bytea, p_digest bytea)
        RETURNS TABLE (tenant_id uuid, user_id uuid, code_expires_at timestamptz)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        #variable_conflict use_column
        BEGIN
            RETURN QUERY
            UPDATE public.sign_in_challenges c SET code_salt = p_salt, code_digest = p_digest
             WHERE c.id = p_id AND c.user_id IS NOT NULL AND c.code_digest IS NULL
               AND c.consumed_at IS NULL AND c.code_expires_at > clock_timestamp()
            RETURNING c.tenant_id, c.user_id, c.code_expires_at;
        END $$
        """
    )
    # Every guess is counted before it is compared, under row locks on the challenge and on the
    # firm's (email) row, so concurrent or fresh challenges never get more than `p_max` guesses
    # in a window. 'ok' hands back the digest for the comparison; the caller then calls
    # `portal_sign_in_missed` or `portal_sign_in_consume`.
    op.execute(
        """
        CREATE FUNCTION portal_sign_in_attempt(
            p_id uuid, p_host text, p_max integer, p_lock_seconds integer
        ) RETURNS TABLE (outcome text, tenant_id uuid, user_id uuid, code_salt bytea,
                         code_digest bytea, tries_left integer, locked_until timestamptz)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        #variable_conflict use_column
        DECLARE
            v_now timestamptz := clock_timestamp();
            v_challenge record;
            v_lock record;
            v_until timestamptz;
        BEGIN
            SELECT * INTO v_challenge FROM public.sign_in_challenges c
             WHERE c.id = p_id AND c.host = lower(p_host) FOR UPDATE;
            IF NOT FOUND THEN
                RETURN QUERY SELECT 'unknown'::text, NULL::uuid, NULL::uuid, NULL::bytea,
                    NULL::bytea, 0, NULL::timestamptz;
                RETURN;
            END IF;
            INSERT INTO public.sign_in_locks (host_tenant_id, email_sha256)
            VALUES (v_challenge.host_tenant_id, v_challenge.email_sha256)
            ON CONFLICT DO NOTHING;
            SELECT * INTO v_lock FROM public.sign_in_locks l
             WHERE l.host_tenant_id = v_challenge.host_tenant_id
               AND l.email_sha256 = v_challenge.email_sha256 FOR UPDATE;
            IF v_lock.locked_until > v_now THEN
                RETURN QUERY SELECT 'locked'::text, NULL::uuid, NULL::uuid, NULL::bytea,
                    NULL::bytea, 0, v_lock.locked_until;
                RETURN;
            END IF;
            IF v_challenge.consumed_at IS NOT NULL THEN
                RETURN QUERY SELECT 'unknown'::text, NULL::uuid, NULL::uuid, NULL::bytea,
                    NULL::bytea, 0, NULL::timestamptz;
                RETURN;
            END IF;
            IF v_challenge.code_expires_at <= v_now THEN
                RETURN QUERY SELECT 'expired'::text, NULL::uuid, NULL::uuid, NULL::bytea,
                    NULL::bytea, 0, NULL::timestamptz;
                RETURN;
            END IF;
            IF v_lock.window_until IS NULL OR v_lock.window_until <= v_now THEN
                UPDATE public.sign_in_locks SET attempts = 0, locked_until = NULL,
                    window_until = v_now + make_interval(secs => p_lock_seconds)
                 WHERE host_tenant_id = v_lock.host_tenant_id
                   AND email_sha256 = v_lock.email_sha256;
                v_lock.attempts := 0;
            END IF;
            UPDATE public.sign_in_locks SET attempts = attempts + 1
             WHERE host_tenant_id = v_lock.host_tenant_id AND email_sha256 = v_lock.email_sha256;
            UPDATE public.sign_in_challenges SET attempts = attempts + 1 WHERE id = p_id;
            IF v_lock.attempts + 1 > p_max THEN
                UPDATE public.sign_in_locks
                   SET locked_until = v_now + make_interval(secs => p_lock_seconds)
                 WHERE host_tenant_id = v_lock.host_tenant_id
                   AND email_sha256 = v_lock.email_sha256
                RETURNING sign_in_locks.locked_until INTO v_until;
                UPDATE public.sign_in_challenges SET consumed_at = v_now WHERE id = p_id;
                RETURN QUERY SELECT 'locked'::text, NULL::uuid, NULL::uuid, NULL::bytea,
                    NULL::bytea, 0, v_until;
                RETURN;
            END IF;
            RETURN QUERY SELECT 'ok'::text, v_challenge.tenant_id, v_challenge.user_id,
                v_challenge.code_salt, v_challenge.code_digest, p_max - (v_lock.attempts + 1),
                NULL::timestamptz;
        END $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION portal_sign_in_missed(p_id uuid, p_max integer, p_lock_seconds integer)
        RETURNS timestamptz
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        DECLARE
            v_challenge record;
            v_until timestamptz;
        BEGIN
            SELECT * INTO v_challenge FROM public.sign_in_challenges WHERE id = p_id;
            IF NOT FOUND THEN
                RETURN NULL;
            END IF;
            -- The last allowed guess missed: lock, or report the lock a concurrent guess set.
            UPDATE public.sign_in_locks
               SET locked_until = CASE WHEN locked_until > clock_timestamp() THEN locked_until
                   ELSE clock_timestamp() + make_interval(secs => p_lock_seconds) END
             WHERE host_tenant_id = v_challenge.host_tenant_id
               AND email_sha256 = v_challenge.email_sha256 AND attempts >= p_max
            RETURNING locked_until INTO v_until;
            IF v_until IS NOT NULL THEN
                UPDATE public.sign_in_challenges SET consumed_at = clock_timestamp()
                 WHERE id = p_id AND consumed_at IS NULL;
            END IF;
            RETURN v_until;
        END $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION portal_sign_in_consume(p_id uuid) RETURNS boolean
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        DECLARE
            v_challenge record;
        BEGIN
            UPDATE public.sign_in_challenges SET consumed_at = clock_timestamp(),
                code_salt = NULL, code_digest = NULL
             WHERE id = p_id AND consumed_at IS NULL
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
    op.execute(
        """
        CREATE FUNCTION portal_sign_in_resend(
            p_id uuid, p_host text, p_code_seconds integer, p_resend_seconds integer
        ) RETURNS TABLE (outcome text, code_expires_at timestamptz,
                         resend_available_at timestamptz, tenant_id uuid, user_id uuid,
                         send boolean)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        #variable_conflict use_column
        DECLARE
            v_now timestamptz := clock_timestamp();
            v_row record;
        BEGIN
            SELECT * INTO v_row FROM public.sign_in_challenges c
             WHERE c.id = p_id AND c.host = lower(p_host) AND c.consumed_at IS NULL FOR UPDATE;
            IF NOT FOUND THEN
                RETURN QUERY SELECT 'unknown'::text, NULL::timestamptz, NULL::timestamptz,
                    NULL::uuid, NULL::uuid, false;
                RETURN;
            END IF;
            IF v_now < v_row.resend_available_at THEN
                RETURN QUERY SELECT 'too_soon'::text, v_row.code_expires_at,
                    v_row.resend_available_at, NULL::uuid, NULL::uuid, false;
                RETURN;
            END IF;
            -- A new code; the old one is void and the attempts are kept.
            UPDATE public.sign_in_challenges c SET code_salt = NULL, code_digest = NULL,
                code_expires_at = v_now + make_interval(secs => p_code_seconds),
                resend_available_at = v_now + make_interval(secs => p_resend_seconds)
             WHERE c.id = p_id;
            RETURN QUERY SELECT 'ok'::text, c.code_expires_at, c.resend_available_at,
                c.tenant_id, c.user_id,
                c.user_id IS NOT NULL AND NOT EXISTS (
                    SELECT 1 FROM public.sign_in_locks l
                     WHERE l.host_tenant_id = c.host_tenant_id
                       AND l.email_sha256 = c.email_sha256 AND l.locked_until > v_now)
              FROM public.sign_in_challenges c WHERE c.id = p_id;
        END $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION portal_session_start(
            p_user_id uuid, p_tenant_id uuid, p_host text, p_access_sha256 text,
            p_access_seconds integer, p_cookie_sha256 text, p_idle_seconds integer,
            p_absolute_seconds integer
        ) RETURNS uuid
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        DECLARE
            v_id uuid;
            v_now timestamptz := clock_timestamp();
        BEGIN
            INSERT INTO public.auth_sessions (user_id, provider, surface, tenant_id, host,
                access_sha256, access_expires_at, idle_expires_at, absolute_expires_at)
            VALUES (p_user_id, 'portal_code', 'portal', p_tenant_id, lower(p_host),
                p_access_sha256, v_now + make_interval(secs => p_access_seconds),
                v_now + make_interval(secs => p_idle_seconds),
                v_now + make_interval(secs => p_absolute_seconds))
            RETURNING id INTO v_id;
            INSERT INTO public.auth_session_cookies (cookie_sha256, session_id)
            VALUES (p_cookie_sha256, v_id);
            RETURN v_id;
        END $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION portal_session_resolve(p_access_sha256 text, p_host text)
        RETURNS TABLE (session_id uuid, user_id uuid, tenant_id uuid)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        #variable_conflict use_column
        BEGIN
            RETURN QUERY
            SELECT s.id, s.user_id, s.tenant_id FROM public.auth_sessions s
             WHERE s.access_sha256 = p_access_sha256 AND s.surface = 'portal'
               AND s.host = lower(p_host) AND s.ended_at IS NULL
               AND s.access_expires_at > clock_timestamp()
               AND s.idle_expires_at > clock_timestamp()
               AND s.absolute_expires_at > clock_timestamp();
        END $$
        """
    )
    op.execute(
        """
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
    )
    op.execute(
        """
        CREATE FUNCTION portal_session_end_id(p_session_id uuid, p_user_id uuid)
        RETURNS uuid
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        DECLARE
            v_id uuid;
        BEGIN
            UPDATE public.auth_sessions SET ended_at = clock_timestamp(), end_reason = 'sign_out'
             WHERE id = p_session_id AND user_id = p_user_id
               AND surface = 'portal' AND ended_at IS NULL
            RETURNING id INTO v_id;
            RETURN v_id;
        END $$
        """
    )
    for function in _FUNCTIONS:
        op.execute(f"REVOKE ALL ON FUNCTION {function} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {function} TO abacus_app")


def downgrade() -> None:
    for function in reversed(_FUNCTIONS):
        op.execute(f"DROP FUNCTION {function}")
    op.execute("ALTER TABLE auth_sessions DROP CONSTRAINT auth_sessions_portal_pinned")
    op.execute(
        "ALTER TABLE auth_sessions DROP COLUMN access_expires_at, DROP COLUMN access_sha256, "
        "DROP COLUMN host, DROP COLUMN tenant_id, DROP COLUMN surface"
    )
    op.execute("ALTER TABLE auth_sessions DROP CONSTRAINT auth_sessions_provider_check")
    op.execute(
        "ALTER TABLE auth_sessions ADD CONSTRAINT auth_sessions_provider_check "
        "CHECK (provider IN ('workos', 'oidc'))"
    )
    op.execute("DROP TABLE sign_in_locks")
    op.execute("DROP TABLE sign_in_challenges")
