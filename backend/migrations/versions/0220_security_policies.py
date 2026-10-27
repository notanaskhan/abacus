"""G-02-T14: the firm's security policies and their enforcement (SPEC-349 AC-15 to AC-20, AC-28;
G-02 §4.2; DEC-22, DEC-34, DEC-35, DEC-72, DEC-524 to DEC-528).

- `security_policies` (new, identity, forced RLS): one row per firm. Require SSO with who
  enforced it and when; the "IdP enforces MFA" attestation; the staff session limits, which may
  only be shorter than the platform's (12 hours absolute, 30 minutes idle: the CHECKs hold the
  ceilings whatever the app sends, and the floors of 60 and 5 minutes keep a firm from locking its
  people out); the one SSO-exempt (break-glass) account, a current member of the firm, never the
  person who designates it (the trigger refuses it); and "Allow support session
  requests" with its own version. A firm without a row reads the defaults. A row is a live
  person's own (`security_policies_actor`, the 0167 pattern), except the stamp of the exempt
  account's last sign-in, which the trigger sets to the database clock itself.
- `portal_security_policies` gains `portal_session_minutes` (15 to 480, default 480: the portal
  session may only be shortened, AC-19) and its writer: the app may insert and update that column
  only (the MFA floor's columns stay read-only), as a live person.
- `auth_session_tenant_revocations` (new, identity, forced RLS, insert-only): "Sign out of
  the firm". A staff session spans firms (`auth_sessions` is global); a row here stops that session
  acting in this firm alone (AC-20).
- `auth_sessions.auth_method` (new, nullable): how the person signed in, as the provider reported
  it (`sso`, `email_code`, `passkey`, `totp`); null when it did not say.

Definers (the app never reads `auth_sessions` itself; each takes the firm from the session's
`app.tenant_id`, never from an argument, except the BFF's request check, which takes the firm
the request chose and answers one boolean about the caller's own session):
- `auth_session_start(..., auth_method)` and `auth_session_rotate(cookie, next, idle, absolute)`:
  overloads of 0101's that record the method and end a session idle or older than the limits the
  BFF passes (the strictest of the person's firms), counted from its last refresh and its start;
- `security_sessions()`: the live sessions of the session firm's active staff, less those signed
  out of this firm;
- `security_session_member(session)`: that session's person, when it is live, theirs is an active
  staff membership of the session firm, and it is not already signed out of it;
- `security_sign_in_methods()`: per active staff member of the session firm, whether they have an
  MFA sign-in, an SSO sign-in and a passkey (hardware key) sign-in on record;
- `auth_session_signed_out(cookie, user, firm)`: whether the request's session (or, without a
  cookie, every live session of the person) has been signed out of that firm;
- `auth_session_owner(cookie)`: the person behind a refresh cookie (the caller holds it);
- `auth_session_purge()`: deletes sessions that ended (or expired) more than a year ago, and their
  cookies (P-01 hand-off: security logs are kept a year, the audit log keeps the events).

Revision ID: 0220
Revises: 0197 (the S11 batch re-points it)
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0220"
down_revision = "0197"
branch_labels = None
depends_on = None

_TENANT = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"
_LIVE = (
    "s.ended_at IS NULL AND clock_timestamp() < s.idle_expires_at "
    "AND clock_timestamp() < s.absolute_expires_at"
)
_FUNCTIONS = (
    "auth_session_start(uuid, text, bytea, timestamptz, text, integer, integer, text)",
    "auth_session_rotate(text, text, integer, integer)",
    "security_sessions()",
    "security_session_member(uuid)",
    "security_sign_in_methods()",
    "auth_session_signed_out(text, uuid, uuid)",
    "auth_session_purge()",
    "auth_session_owner(text)",
)


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE auth_sessions ADD COLUMN auth_method text NULL
            CHECK (auth_method IN ('sso', 'email_code', 'passkey', 'totp'))
        """
    )
    op.execute(
        """
        CREATE TABLE security_policies (
            tenant_id uuid PRIMARY KEY REFERENCES firms (tenant_id),
            require_sso boolean NOT NULL DEFAULT false,
            sso_enforced_at timestamptz NULL,
            sso_enforced_by uuid NULL,
            idp_mfa_attested_at timestamptz NULL,
            idp_mfa_attested_by uuid NULL,
            session_absolute_minutes integer NOT NULL DEFAULT 720
                CHECK (session_absolute_minutes BETWEEN 60 AND 720),
            session_idle_minutes integer NOT NULL DEFAULT 30
                CHECK (session_idle_minutes BETWEEN 5 AND 30),
            sso_exempt_user_id uuid NULL,
            sso_exempt_tested_at timestamptz NULL,
            allow_support_requests boolean NOT NULL DEFAULT true,
            support_updated_at timestamptz NULL,
            support_updated_by uuid NULL,
            version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
            support_version integer NOT NULL DEFAULT 0 CHECK (support_version >= 0),
            updated_by uuid NOT NULL,
            updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            CONSTRAINT security_policies_sso_enforced CHECK (
                NOT require_sso OR (sso_enforced_at IS NOT NULL AND sso_enforced_by IS NOT NULL)),
            CONSTRAINT security_policies_attested CHECK (
                (idp_mfa_attested_at IS NULL) = (idp_mfa_attested_by IS NULL)),
            FOREIGN KEY (tenant_id, sso_exempt_user_id) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    tenant_table(op, "security_policies")
    insert_columns(
        op,
        "security_policies",
        (
            "tenant_id",
            "require_sso",
            "sso_enforced_at",
            "sso_enforced_by",
            "idp_mfa_attested_at",
            "idp_mfa_attested_by",
            "session_absolute_minutes",
            "session_idle_minutes",
            "sso_exempt_user_id",
            "allow_support_requests",
            "support_updated_at",
            "support_updated_by",
            "support_version",
            "updated_by",
        ),
    )
    op.execute("REVOKE UPDATE, DELETE ON security_policies FROM abacus_app")
    op.execute(
        "GRANT UPDATE (require_sso, sso_enforced_at, sso_enforced_by, idp_mfa_attested_at, "
        "idp_mfa_attested_by, session_absolute_minutes, session_idle_minutes, "
        "sso_exempt_user_id, sso_exempt_tested_at, allow_support_requests, support_updated_at, "
        "support_updated_by, version, support_version, updated_by, updated_at) "
        "ON security_policies TO abacus_app"
    )
    # A policy is a live person's own; the exempt account's sign-in stamp alone is the database's
    # (any value the app sends becomes the database clock, and it changes nothing else).
    op.execute(
        """
        CREATE FUNCTION security_policies_actor() RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = pg_catalog, public, pg_temp
        AS $$
        BEGIN
            IF TG_OP = 'UPDATE'
               AND (to_jsonb(NEW) - 'sso_exempt_tested_at')
                   = (to_jsonb(OLD) - 'sso_exempt_tested_at') THEN
                IF NEW.sso_exempt_tested_at IS DISTINCT FROM OLD.sso_exempt_tested_at THEN
                    IF OLD.sso_exempt_user_id IS NULL THEN
                        RAISE EXCEPTION 'no SSO-exempt account to stamp'
                            USING ERRCODE = 'insufficient_privilege';
                    END IF;
                    NEW.sso_exempt_tested_at := clock_timestamp();
                END IF;
                RETURN NEW;
            END IF;
            IF current_setting('app.actor_kind', true) IS DISTINCT FROM 'human'
               OR NEW.updated_by::text IS DISTINCT FROM current_setting('app.actor_id', true) THEN
                RAISE EXCEPTION 'a security policy is a live person''s own'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF (TG_OP = 'INSERT' OR NEW.sso_exempt_user_id IS DISTINCT FROM OLD.sso_exempt_user_id)
               AND NEW.sso_exempt_user_id = NEW.updated_by THEN
                RAISE EXCEPTION 'nobody designates themselves the SSO-exempt account'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF TG_OP = 'INSERT' THEN
                NEW.sso_exempt_tested_at := NULL;
            ELSIF NEW.sso_exempt_user_id IS DISTINCT FROM OLD.sso_exempt_user_id THEN
                NEW.sso_exempt_tested_at := NULL;  -- a new account has not been tested yet
            ELSE
                NEW.sso_exempt_tested_at := OLD.sso_exempt_tested_at;
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER security_policies_actor BEFORE INSERT OR UPDATE "
        "ON security_policies FOR EACH ROW EXECUTE FUNCTION security_policies_actor()"
    )

    # The portal's session length (AC-19): shorter only, and G-02's writer for this column alone.
    op.execute(
        """
        ALTER TABLE portal_security_policies
            ADD COLUMN portal_session_minutes smallint NOT NULL DEFAULT 480
                CHECK (portal_session_minutes BETWEEN 15 AND 480)
        """
    )
    op.execute(
        "GRANT INSERT (tenant_id, portal_session_minutes, updated_by) "
        "ON portal_security_policies TO abacus_app"
    )
    op.execute(
        "GRANT UPDATE (portal_session_minutes, version, updated_by, updated_at) "
        "ON portal_security_policies TO abacus_app"
    )
    op.execute(
        """
        CREATE FUNCTION portal_security_policies_actor() RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = pg_catalog, public, pg_temp
        AS $$
        BEGIN
            -- The app's writes are a live person's (G-02's writer); P-08's floor columns stay
            -- the platform's and the seed's, which write as the owner.
            IF current_user = 'abacus_app' AND (
               current_setting('app.actor_kind', true) IS DISTINCT FROM 'human'
               OR NEW.updated_by IS NULL
               OR NEW.updated_by::text IS DISTINCT FROM current_setting('app.actor_id', true)) THEN
                RAISE EXCEPTION 'a portal security policy is a live person''s own'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER portal_security_policies_actor BEFORE INSERT OR UPDATE "
        "ON portal_security_policies FOR EACH ROW "
        "EXECUTE FUNCTION portal_security_policies_actor()"
    )

    op.execute(
        """
        CREATE TABLE auth_session_tenant_revocations (
            tenant_id uuid NOT NULL REFERENCES firms (tenant_id),
            session_id uuid NOT NULL,
            revoked_by uuid NOT NULL,
            revoked_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            PRIMARY KEY (tenant_id, session_id),
            CONSTRAINT auth_session_tenant_revocations_by_member
                FOREIGN KEY (tenant_id, revoked_by) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    tenant_table(op, "auth_session_tenant_revocations")
    insert_only(op, "auth_session_tenant_revocations")
    insert_columns(
        op, "auth_session_tenant_revocations", ("tenant_id", "session_id", "revoked_by")
    )
    op.execute(
        """
        CREATE FUNCTION auth_session_tenant_revocations_actor() RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = pg_catalog, public, pg_temp
        AS $$
        BEGIN
            IF current_setting('app.actor_kind', true) IS DISTINCT FROM 'human'
               OR NEW.revoked_by::text IS DISTINCT FROM current_setting('app.actor_id', true) THEN
                RAISE EXCEPTION 'signing a session out is a live person''s act'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER auth_session_tenant_revocations_actor BEFORE INSERT "
        "ON auth_session_tenant_revocations FOR EACH ROW "
        "EXECUTE FUNCTION auth_session_tenant_revocations_actor()"
    )

    op.execute(
        """
        CREATE FUNCTION auth_session_start(
            p_user_id uuid, p_provider text, p_refresh bytea, p_mfa_at timestamptz,
            p_cookie_sha256 text, p_idle_seconds integer, p_absolute_seconds integer,
            p_auth_method text
        ) RETURNS uuid
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        DECLARE
            v_id uuid;
        BEGIN
            INSERT INTO public.auth_sessions (user_id, provider, provider_refresh_enc, mfa_at,
                idle_expires_at, absolute_expires_at, auth_method)
            VALUES (p_user_id, p_provider, p_refresh, p_mfa_at,
                clock_timestamp() + make_interval(secs => p_idle_seconds),
                clock_timestamp() + make_interval(secs => p_absolute_seconds), p_auth_method)
            RETURNING id INTO v_id;
            INSERT INTO public.auth_session_cookies (cookie_sha256, session_id)
            VALUES (p_cookie_sha256, v_id);
            RETURN v_id;
        END $$
        """
    )
    # 0101's rotation, with the absolute limit too, and both counted from the session's own
    # times, so a firm that shortens its limits ends an older session at its next refresh.
    op.execute(
        """
        CREATE FUNCTION auth_session_rotate(
            p_cookie_sha256 text, p_new_cookie_sha256 text, p_idle_seconds integer,
            p_absolute_seconds integer
        ) RETURNS TABLE (outcome text, session_id uuid, user_id uuid, provider_refresh_enc bytea,
                         mfa_at timestamptz, auth_method text)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        #variable_conflict use_column
        DECLARE
            v_cookie record;
            v_session record;
            v_now timestamptz := clock_timestamp();
            v_reason text;
            v_absolute timestamptz;
        BEGIN
            SELECT c.session_id, c.retired_at INTO v_cookie
              FROM public.auth_session_cookies c WHERE c.cookie_sha256 = p_cookie_sha256;
            IF NOT FOUND THEN
                RETURN QUERY SELECT 'unknown'::text, NULL::uuid, NULL::uuid, NULL::bytea,
                    NULL::timestamptz, NULL::text;
                RETURN;
            END IF;
            SELECT * INTO v_session FROM public.auth_sessions s
             WHERE s.id = v_cookie.session_id FOR UPDATE;
            IF v_session.ended_at IS NOT NULL THEN
                RETURN QUERY SELECT 'ended'::text, v_session.id, v_session.user_id,
                    NULL::bytea, NULL::timestamptz, NULL::text;
                RETURN;
            END IF;
            IF v_cookie.retired_at IS NOT NULL THEN
                UPDATE public.auth_sessions SET ended_at = v_now, end_reason = 'reuse_detected'
                 WHERE id = v_session.id;
                RETURN QUERY SELECT 'reused'::text, v_session.id, v_session.user_id,
                    NULL::bytea, NULL::timestamptz, NULL::text;
                RETURN;
            END IF;
            v_absolute := least(v_session.absolute_expires_at,
                                v_session.created_at + make_interval(secs => p_absolute_seconds));
            IF v_now >= v_absolute
               OR v_now >= least(v_session.idle_expires_at,
                                 v_session.last_seen_at + make_interval(secs => p_idle_seconds))
            THEN
                v_reason := CASE WHEN v_now >= v_absolute THEN 'absolute' ELSE 'idle' END;
                UPDATE public.auth_sessions SET ended_at = v_now, end_reason = v_reason
                 WHERE id = v_session.id;
                RETURN QUERY SELECT v_reason, v_session.id, v_session.user_id,
                    NULL::bytea, NULL::timestamptz, NULL::text;
                RETURN;
            END IF;
            UPDATE public.auth_session_cookies SET retired_at = v_now
             WHERE cookie_sha256 = p_cookie_sha256;
            INSERT INTO public.auth_session_cookies (cookie_sha256, session_id)
            VALUES (p_new_cookie_sha256, v_session.id);
            UPDATE public.auth_sessions SET last_seen_at = v_now,
                idle_expires_at = least(v_now + make_interval(secs => p_idle_seconds), v_absolute)
             WHERE id = v_session.id;
            RETURN QUERY SELECT 'ok'::text, v_session.id, v_session.user_id,
                v_session.provider_refresh_enc, v_session.mfa_at, v_session.auth_method;
        END $$
        """
    )
    op.execute(
        f"""
        CREATE FUNCTION security_sessions()
        RETURNS TABLE (id uuid, user_id uuid, created_at timestamptz, last_seen_at timestamptz,
                       mfa_at timestamptz, auth_method text)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp
        SET statement_timeout = '5s' AS $$
            SELECT s.id, s.user_id, s.created_at, s.last_seen_at, s.mfa_at, s.auth_method
              FROM public.auth_sessions s
              JOIN public.memberships m ON m.user_id = s.user_id
             WHERE m.tenant_id = {_TENANT} AND m.kind = 'staff' AND m.status = 'active'
               AND {_LIVE}
               AND NOT EXISTS (
                   SELECT 1 FROM public.auth_session_tenant_revocations r
                    WHERE r.tenant_id = m.tenant_id AND r.session_id = s.id)
             ORDER BY s.last_seen_at DESC, s.id
             LIMIT 1000
        $$
        """  # noqa: S608 -- module constants only
    )
    op.execute(
        f"""
        CREATE FUNCTION security_session_member(p_session_id uuid) RETURNS uuid
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp
        SET statement_timeout = '5s' AS $$
            SELECT s.user_id
              FROM public.auth_sessions s
              JOIN public.memberships m ON m.user_id = s.user_id
             WHERE s.id = p_session_id
               AND m.tenant_id = {_TENANT} AND m.kind = 'staff' AND m.status = 'active'
               AND {_LIVE}
               AND NOT EXISTS (
                   SELECT 1 FROM public.auth_session_tenant_revocations r
                    WHERE r.tenant_id = m.tenant_id AND r.session_id = s.id)
        $$
        """  # noqa: S608 -- module constants only
    )
    op.execute(
        f"""
        CREATE FUNCTION security_sign_in_methods()
        RETURNS TABLE (user_id uuid, mfa boolean, sso boolean, passkey boolean)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp
        SET statement_timeout = '5s' AS $$
            SELECT m.user_id,
                   bool_or(s.mfa_at IS NOT NULL),
                   bool_or(s.auth_method = 'sso'),
                   bool_or(s.auth_method = 'passkey')
              FROM public.memberships m
              JOIN public.auth_sessions s ON s.user_id = m.user_id
             WHERE m.tenant_id = {_TENANT} AND m.kind = 'staff' AND m.status = 'active'
             GROUP BY m.user_id
        $$
        """  # noqa: S608 -- module constants only
    )
    # The BFF's request check: the firm is the one the request chose (the caller already holds
    # an active membership there); the answer is one boolean about the caller's own session.
    op.execute(
        f"""
        CREATE FUNCTION auth_session_signed_out(
            p_cookie_sha256 text, p_user_id uuid, p_tenant_id uuid
        ) RETURNS boolean
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp
        SET statement_timeout = '5s' AS $$
        DECLARE
            v_previous text := current_setting('app.tenant_id', true);
            v_session uuid;
            v_out boolean := false;
        BEGIN
            PERFORM set_config('app.tenant_id', p_tenant_id::text, true);
            IF p_cookie_sha256 IS NOT NULL THEN
                SELECT c.session_id INTO v_session
                  FROM public.auth_session_cookies c
                  JOIN public.auth_sessions s ON s.id = c.session_id
                 WHERE c.cookie_sha256 = p_cookie_sha256 AND s.user_id = p_user_id;
            END IF;
            IF v_session IS NOT NULL THEN
                v_out := EXISTS (
                    SELECT 1 FROM public.auth_session_tenant_revocations r
                     WHERE r.tenant_id = p_tenant_id AND r.session_id = v_session);
            ELSE
                -- No session cookie (a bearer token alone): refused once the person has been
                -- signed out here and holds no live session that has not been.
                v_out := EXISTS (
                    SELECT 1 FROM public.auth_session_tenant_revocations r
                      JOIN public.auth_sessions s ON s.id = r.session_id
                     WHERE r.tenant_id = p_tenant_id AND s.user_id = p_user_id)
                  AND NOT EXISTS (
                    SELECT 1 FROM public.auth_sessions s
                     WHERE s.user_id = p_user_id AND {_LIVE}
                       AND NOT EXISTS (
                           SELECT 1 FROM public.auth_session_tenant_revocations r
                            WHERE r.tenant_id = p_tenant_id AND r.session_id = s.id));
            END IF;
            PERFORM set_config('app.tenant_id', coalesce(v_previous, ''), true);
            RETURN v_out;
        END $$
        """  # noqa: S608 -- module constants only
    )
    # The person behind a refresh cookie, so the BFF can read their firms' limits first.
    op.execute(
        """
        CREATE FUNCTION auth_session_owner(p_cookie_sha256 text) RETURNS uuid
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp
        SET statement_timeout = '5s' AS $$
            SELECT s.user_id FROM public.auth_session_cookies c
              JOIN public.auth_sessions s ON s.id = c.session_id
             WHERE c.cookie_sha256 = p_cookie_sha256
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION auth_session_purge() RETURNS integer
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp
        SET statement_timeout = '60s' AS $$
        DECLARE
            v_count integer;
        BEGIN
            WITH doomed AS (
                SELECT s.id FROM public.auth_sessions s
                 WHERE coalesce(s.ended_at, least(s.absolute_expires_at, s.idle_expires_at))
                       < clock_timestamp() - interval '1 year'
                 LIMIT 10000
            ), cookies AS (
                DELETE FROM public.auth_session_cookies c USING doomed d
                 WHERE c.session_id = d.id
            ), sessions AS (
                DELETE FROM public.auth_sessions s USING doomed d WHERE s.id = d.id
                RETURNING s.id
            )
            SELECT count(*) INTO v_count FROM sessions;
            RETURN v_count;
        END $$
        """
    )
    for function in _FUNCTIONS:
        op.execute(f"REVOKE ALL ON FUNCTION {function} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {function} TO abacus_app")


def downgrade() -> None:
    for function in reversed(_FUNCTIONS):
        op.execute(f"DROP FUNCTION {function}")
    op.execute("DROP TABLE auth_session_tenant_revocations")
    op.execute("DROP FUNCTION auth_session_tenant_revocations_actor()")
    op.execute("DROP TRIGGER portal_security_policies_actor ON portal_security_policies")
    op.execute("DROP FUNCTION portal_security_policies_actor()")
    op.execute("REVOKE INSERT, UPDATE ON portal_security_policies FROM abacus_app")
    op.execute("ALTER TABLE portal_security_policies DROP COLUMN portal_session_minutes")
    op.execute("DROP TABLE security_policies")
    op.execute("DROP FUNCTION security_policies_actor()")
    op.execute("ALTER TABLE auth_sessions DROP COLUMN auth_method")
