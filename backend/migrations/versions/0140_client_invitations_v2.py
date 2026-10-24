"""P-08-T18: invitations v2 (SPEC-320 AC-12, AC-13; DEC-35; DEC-275).

`client_invitations` gains what POR-01 d needs and what acceptance creates: the invitation's
`kind` (`firm_invite`, `colleague`, `outside_org`, `delegate`), the contact it is for, a
`grant_template` (one role on one scope kind over 1 to 200 scope ids, CHECKed here and validated
again by identity), the terms (`terms_version`, `terms_url`) and when they were accepted, and the
renewal count P-08-T21 uses (at most 2). New invitations last 14 days (identity's
`INVITATION_DAYS`); pending rows keep the expiry they were issued with.

Definers (no tenant is known before the token is):

- `portal_invitation_preview`: the host's firm, the token's invitation in that firm, live, and not
  addressed to a staff member of the firm; every miss is counted per identity (an IP digest) in
  `invitation_failures`, and ten misses in an hour answer nothing for 15 minutes, as
  `invitation_token_find` does (0025). Every failure is the same empty answer.
- `portal_invitation_start`: `auth/start` with an invitation token. For a live invitation of the
  host's firm addressed to the email typed (and not a staff member's), the invitee is found (a
  client of the firm with that email) or provisioned (a user row, no membership) and the
  challenge names them; anything else is exactly the ordinary `portal_sign_in_start`.
- `portal_invitee_resolve`: a live portal session on its host, without the membership and grant
  test `portal_context` adds, with the person's email and `mfa_at` (acceptance only).
- `portal_access_revoke_except`: `portal_access_revoke` (0133) less the session accepting.
- `portal_mfa_begin_session`: the accepting session ends and a used challenge carries a
  second-step token, so the new grants' MFA floor is met through T17's `/mfa` routes.

Revision ID: 0140
Revises: 0133
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns

revision = "0140"
down_revision = "0133"
branch_labels = None
depends_on = None

_FUNCTIONS = (
    "portal_invitation_preview(text, text, text)",
    "portal_invitation_start(text, text, text, integer, integer)",
    "portal_invitee_resolve(text, text)",
    "portal_access_revoke_except(uuid, uuid, uuid)",
    "portal_mfa_begin_session(uuid, uuid, text, text, integer)",
)
_INSERT_V1 = ("id", "tenant_id", "engagement_id", "email", "role", "invited_by", "expires_at")
_INSERT_V2 = ("kind", "contact_id", "grant_template", "terms_version", "terms_url")
_ROLES = (
    "'owner', 'contributor', 'plan_administrator', 'trustee', 'taxpayer', 'spouse', "
    "'delegate', 'third_party', 'k1_recipient', 'tcwg', 'prospect', 'component_auditor'"
)
_KINDS = (
    "'client', 'client_entity', 'engagement', 'work_item', 'request_item', 'k1_package', "
    "'governance_room', 'component', 'intake'"
)


def upgrade() -> None:
    op.execute(
        f"""
        ALTER TABLE client_invitations
            ADD COLUMN kind text NOT NULL DEFAULT 'firm_invite'
                CHECK (kind IN ('firm_invite', 'colleague', 'outside_org', 'delegate')),
            ADD COLUMN contact_id uuid NULL,
            ADD COLUMN grant_template jsonb NULL,
            ADD COLUMN terms_version integer NULL CHECK (terms_version >= 1),
            ADD COLUMN terms_url text NULL
                CHECK (terms_url ~ '^https://' AND length(terms_url) <= 500),
            ADD COLUMN terms_accepted_at timestamptz NULL,
            ADD COLUMN renewal_count smallint NOT NULL DEFAULT 0
                CHECK (renewal_count BETWEEN 0 AND 2),
            ADD CONSTRAINT client_invitations_contact
                FOREIGN KEY (tenant_id, contact_id) REFERENCES contacts (tenant_id, id),
            ADD CONSTRAINT client_invitations_template CHECK (
                grant_template IS NULL OR (
                    jsonb_typeof(grant_template) = 'object'
                    AND grant_template->>'role' IN ({_ROLES})
                    AND grant_template->>'scope_kind' IN ({_KINDS})
                    AND jsonb_typeof(grant_template->'scope_ids') = 'array'
                    AND jsonb_array_length(grant_template->'scope_ids') BETWEEN 1 AND 200)),
            ADD CONSTRAINT client_invitations_terms CHECK (
                terms_accepted_at IS NULL OR status = 'accepted')
        """
    )
    insert_columns(op, "client_invitations", _INSERT_V1 + _INSERT_V2)
    op.execute("GRANT UPDATE (terms_accepted_at) ON client_invitations TO abacus_app")

    # Misses are counted as `invitation_token_find` (0025) counts them: ten in an hour, then
    # nothing for 15 minutes.
    op.execute(
        """
        CREATE FUNCTION portal_invitation_preview(
            p_host text, p_token_sha256 text, p_identity text
        ) RETURNS TABLE (tenant_id uuid, invitation_id uuid, engagement_id uuid, email text,
                         kind text, contact_id uuid, grant_template jsonb, terms_url text,
                         terms_version integer, expires_at timestamptz)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp
        SET statement_timeout = '5s' AS $$
        #variable_conflict use_column
        DECLARE
            v_previous text := current_setting('app.tenant_id', true);
            v_firm uuid;
            v_invitation uuid;
            v_found boolean := false;
        BEGIN
            IF (SELECT count(*) FROM public.invitation_failures f
                 WHERE f.identity_hash = p_identity
                   AND f.failed_at > clock_timestamp() - interval '1 hour') >= 10
               AND (SELECT max(f.failed_at) FROM public.invitation_failures f
                     WHERE f.identity_hash = p_identity)
                   > clock_timestamp() - interval '15 minutes' THEN
                RETURN;
            END IF;
            SELECT d.tenant_id INTO v_firm FROM public.portal_domains d
             WHERE d.hostname = lower(p_host) AND d.status = 'active';
            SELECT t.invitation_id INTO v_invitation FROM public.invitation_tokens t
             WHERE t.token_hash = p_token_sha256 AND t.tenant_id = v_firm;
            IF v_invitation IS NOT NULL THEN
                PERFORM set_config('app.tenant_id', v_firm::text, true);
                RETURN QUERY
                SELECT i.tenant_id, i.id, i.engagement_id, i.email, i.kind, i.contact_id,
                       i.grant_template, i.terms_url, i.terms_version, i.expires_at
                  FROM public.client_invitations i
                 WHERE i.id = v_invitation AND i.status = 'pending'
                   AND i.expires_at > clock_timestamp()
                   AND NOT EXISTS (
                       SELECT 1 FROM public.users u
                         JOIN public.memberships m ON m.user_id = u.id
                        WHERE m.tenant_id = v_firm AND m.kind = 'staff'
                          AND lower(u.email) = lower(i.email));
                v_found := FOUND;
                PERFORM set_config('app.tenant_id', coalesce(v_previous, ''), true);
            END IF;
            IF NOT v_found THEN
                INSERT INTO public.invitation_failures (identity_hash) VALUES (p_identity);
                DELETE FROM public.invitation_failures
                 WHERE failed_at < clock_timestamp() - interval '1 day';
            END IF;
        END $$
        """
    )
    # The invitee before any grant: eligible only for a live invitation of the host's firm sent
    # to the address typed. Anything else is the ordinary start, so the answer never says which.
    op.execute(
        """
        CREATE FUNCTION portal_invitation_start(
            p_host text, p_email text, p_token_sha256 text, p_code_seconds integer,
            p_resend_seconds integer
        ) RETURNS TABLE (challenge_id uuid, code_expires_at timestamptz,
                         resend_available_at timestamptz, tenant_id uuid, user_id uuid,
                         send boolean)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp
        SET statement_timeout = '5s' AS $$
        #variable_conflict use_column
        DECLARE
            v_now timestamptz := clock_timestamp();
            v_previous text := current_setting('app.tenant_id', true);
            v_email text := lower(trim(p_email));
            v_email_sha text := encode(sha256(convert_to(lower(trim(p_email)), 'UTF8')), 'hex');
            v_host text := lower(p_host);
            v_firm uuid;
            v_invitation uuid;
            v_eligible boolean := false;
            v_user uuid;
            v_held boolean;
            v_id uuid;
        BEGIN
            SELECT d.tenant_id INTO v_firm FROM public.portal_domains d
             WHERE d.hostname = v_host AND d.status = 'active';
            SELECT t.invitation_id INTO v_invitation FROM public.invitation_tokens t
             WHERE t.token_hash = p_token_sha256 AND t.tenant_id = v_firm;
            IF v_invitation IS NOT NULL THEN
                PERFORM set_config('app.tenant_id', v_firm::text, true);
                SELECT EXISTS (
                    SELECT 1 FROM public.client_invitations i
                     WHERE i.id = v_invitation AND i.status = 'pending'
                       AND i.expires_at > v_now AND lower(i.email) = v_email)
                   AND NOT EXISTS (
                    SELECT 1 FROM public.users u
                      JOIN public.memberships m ON m.user_id = u.id
                     WHERE m.tenant_id = v_firm AND m.kind = 'staff'
                       AND lower(u.email) = v_email)
                  INTO v_eligible;
                IF v_eligible THEN
                    SELECT u.id INTO v_user FROM public.users u
                      JOIN public.memberships m ON m.user_id = u.id AND m.tenant_id = v_firm
                     WHERE lower(u.email) = v_email AND m.kind = 'client'
                     ORDER BY u.created_at LIMIT 1;
                END IF;
                PERFORM set_config('app.tenant_id', coalesce(v_previous, ''), true);
            END IF;
            IF NOT v_eligible THEN
                RETURN QUERY SELECT * FROM public.portal_sign_in_start(
                    p_host, p_email, p_code_seconds, p_resend_seconds);
                RETURN;
            END IF;
            IF v_user IS NULL THEN
                -- One user per invited address: no membership until the invitation is accepted.
                INSERT INTO public.users (idp_issuer, idp_subject, email, display_name)
                VALUES ('urn:abacus:portal-invitee', v_email_sha, trim(p_email),
                        coalesce(nullif(left(split_part(trim(p_email), '@', 1), 200), ''),
                                 'Client'))
                ON CONFLICT (idp_issuer, idp_subject) DO NOTHING;
                SELECT u.id INTO v_user FROM public.users u
                 WHERE u.idp_issuer = 'urn:abacus:portal-invitee'
                   AND u.idp_subject = v_email_sha;
            END IF;
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
            VALUES (v_host, v_firm, v_email_sha, v_firm, v_user,
                v_now + make_interval(secs => p_code_seconds),
                v_now + make_interval(secs => p_resend_seconds))
            RETURNING id INTO v_id;
            RETURN QUERY SELECT c.id, c.code_expires_at, c.resend_available_at, c.tenant_id,
                c.user_id, NOT v_held
              FROM public.sign_in_challenges c WHERE c.id = v_id;
        END $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION portal_invitee_resolve(p_access_sha256 text, p_host text)
        RETURNS TABLE (session_id uuid, user_id uuid, tenant_id uuid, email text,
                       mfa_at timestamptz)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        #variable_conflict use_column
        BEGIN
            RETURN QUERY
            SELECT s.id, s.user_id, s.tenant_id, u.email, s.mfa_at
              FROM public.auth_sessions s JOIN public.users u ON u.id = s.user_id
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
        CREATE FUNCTION portal_access_revoke_except(
            p_tenant_id uuid, p_user_id uuid, p_keep uuid
        ) RETURNS TABLE (kind text, id uuid)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        #variable_conflict use_column
        BEGIN
            RETURN QUERY
            WITH ended AS (
                UPDATE public.auth_sessions s SET ended_at = clock_timestamp(),
                    end_reason = 'revoked'
                 WHERE s.user_id = p_user_id AND s.tenant_id = p_tenant_id
                   AND s.surface = 'portal' AND s.ended_at IS NULL AND s.id <> p_keep
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
    op.execute(
        """
        CREATE FUNCTION portal_mfa_begin_session(
            p_session_id uuid, p_user_id uuid, p_token_sha256 text, p_kind text,
            p_seconds integer
        ) RETURNS boolean
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        DECLARE
            v_now timestamptz := clock_timestamp();
            v_session record;
        BEGIN
            UPDATE public.auth_sessions s SET ended_at = v_now, end_reason = 'revoked'
             WHERE s.id = p_session_id AND s.user_id = p_user_id AND s.surface = 'portal'
               AND s.ended_at IS NULL
            RETURNING s.host, s.tenant_id INTO v_session;
            IF NOT FOUND THEN
                RETURN false;
            END IF;
            INSERT INTO public.sign_in_challenges (host, host_tenant_id, email_sha256, tenant_id,
                user_id, code_expires_at, resend_available_at, consumed_at, mfa_token_sha256,
                mfa_kind, mfa_expires_at)
            SELECT v_session.host, v_session.tenant_id,
                   encode(sha256(convert_to(lower(trim(u.email)), 'UTF8')), 'hex'),
                   v_session.tenant_id, p_user_id, v_now, v_now, v_now, p_token_sha256, p_kind,
                   v_now + make_interval(secs => p_seconds)
              FROM public.users u WHERE u.id = p_user_id;
            RETURN true;
        END $$
        """
    )
    for function in _FUNCTIONS:
        op.execute(f"REVOKE ALL ON FUNCTION {function} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {function} TO abacus_app")


def downgrade() -> None:
    for function in reversed(_FUNCTIONS):
        op.execute(f"DROP FUNCTION {function}")
    op.execute("REVOKE UPDATE (terms_accepted_at) ON client_invitations FROM abacus_app")
    insert_columns(op, "client_invitations", _INSERT_V1)
    op.execute(
        "ALTER TABLE client_invitations DROP CONSTRAINT client_invitations_terms, "
        "DROP CONSTRAINT client_invitations_template, "
        "DROP CONSTRAINT client_invitations_contact, DROP COLUMN renewal_count, "
        "DROP COLUMN terms_accepted_at, DROP COLUMN terms_url, DROP COLUMN terms_version, "
        "DROP COLUMN grant_template, DROP COLUMN contact_id, DROP COLUMN kind"
    )
