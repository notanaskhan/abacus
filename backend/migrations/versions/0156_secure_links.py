"""P-08-T21: secure links and recovery (SPEC-320 AC-14, AC-18 to AC-20; ADR-168; ADR-157).

- `secure_links` (communications, tenant, forced RLS): a link a portal email carries for one
  contact (`reminder`, `invitation`, `signature_request`, `deliverable_ready`, `reconnect`),
  lasting 14 days, single use. Only the token's SHA-256 is kept (`token_sha256`); a renewed
  link's token is issued at delivery, so it is NULL until then. `recipient_email` is the address
  the link was sent to: a renewal goes there and nowhere else. The app inserts, reads, and may
  set only the token at delivery and the revocation.
- Pre-session definers (no tenant before sign-in; the host names the firm, as 0116's do):
  `portal_link_claim` (start with a link: `bad` for any link that is unknown, of another firm,
  used, revoked or expired; `claimed` when the typed address is the link's, which uses it;
  `other` otherwise), `portal_link_renew` (a new link, same contact, purpose, target and
  address, for any link of the host's firm that is not revoked and has fewer than
  `p_per_hour` renewals in the last hour), `portal_invitation_find` (the firm and invitation an
  invitation token names on its own firm's host), and `portal_host_tenant` (the host's firm, for
  the sign-in pause; never returned to the visitor).
- Firm-side recovery definers, in the session's firm only (`app.tenant_id`) and only for a
  person who is a client of that firm (anyone else: nothing happens): `portal_mfa_reset` (the
  person's factor and backup codes removed, their trusted devices in the firm revoked as
  `mfa_reset`, their portal sessions in the firm ended) and `portal_mfa_unlock` (the factor's
  second-step lock cleared).
- `client_invitations.renewal_count` becomes updatable by the app (a recipient's renewal, at most
  twice: the column's CHECK).
- ADR-157's one spelling: the `portal_sign_in_disabled` control becomes `portal_sign_in` (the
  stored value and the `control_active` name). Existing rows are renamed; the insert-only change
  history keeps its old rows, so its CHECK allows both.

Revision ID: 0156
Revises: 0146
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0156"
down_revision = "0146"
branch_labels = None
depends_on = None

_SHA = "~ '^[0-9a-f]{64}$'"
_PURPOSES = "'reminder', 'invitation', 'signature_request', 'deliverable_ready', 'reconnect'"
_FUNCTIONS = (
    "portal_host_tenant(text)",
    "portal_link_claim(text, text, text)",
    "portal_link_renew(text, text, integer, integer)",
    "portal_invitation_find(text, text)",
    "portal_mfa_reset(uuid)",
    "portal_mfa_unlock(uuid)",
)
_CONTROLS = "'ai_pause', 'model_route_block', 'email_pause', 'read_only'"
_CONTROLS_V1 = f"{_CONTROLS}, 'portal_sign_in_disabled'"
_CONTROLS_V2 = f"{_CONTROLS}, 'portal_sign_in'"
_CONTROLS_HISTORY = f"{_CONTROLS}, 'portal_sign_in', 'portal_sign_in_disabled'"


def _controls_check(table: str, values: str) -> None:
    op.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {table}_control_check")
    op.execute(
        f"ALTER TABLE {table} ADD CONSTRAINT {table}_control_check CHECK (control IN ({values}))"
    )


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE secure_links (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES firms (tenant_id),
            contact_id uuid NOT NULL,
            purpose text NOT NULL CHECK (purpose IN ({_PURPOSES})),
            target_kind text NULL CHECK (target_kind ~ '^[a-z][a-z_]{{0,39}}$'),
            target_id uuid NULL,
            recipient_email text NOT NULL
                CHECK (length(recipient_email) BETWEEN 3 AND 320
                       AND recipient_email = lower(trim(recipient_email))),
            host text NULL CHECK (length(host) BETWEEN 1 AND 253),
            token_sha256 text NULL UNIQUE CHECK (token_sha256 {_SHA}),
            issued_by uuid NULL,
            issued_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            expires_at timestamptz NOT NULL,
            used_at timestamptz NULL,
            renewed_from_id uuid NULL REFERENCES secure_links (id),
            revoked_at timestamptz NULL,
            CHECK (expires_at > issued_at),
            CHECK ((target_kind IS NULL) = (target_id IS NULL))
        )
        """
    )
    op.execute("CREATE INDEX secure_links_contact ON secure_links (tenant_id, contact_id)")
    op.execute(
        "CREATE INDEX secure_links_renewed ON secure_links (renewed_from_id, issued_at) "
        "WHERE renewed_from_id IS NOT NULL"
    )
    tenant_table(op, "secure_links")
    op.execute("REVOKE UPDATE, DELETE ON secure_links FROM abacus_app")
    insert_columns(
        op,
        "secure_links",
        (
            *("id", "tenant_id", "contact_id", "purpose", "target_kind", "target_id"),
            *("recipient_email", "host", "token_sha256", "issued_by", "expires_at"),
        ),
    )
    op.execute("GRANT UPDATE (token_sha256, revoked_at) ON secure_links TO abacus_app")
    op.execute("GRANT UPDATE (renewal_count) ON client_invitations TO abacus_app")

    op.execute(
        """
        CREATE FUNCTION portal_host_tenant(p_host text) RETURNS uuid
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp
        SET statement_timeout = '5s' AS $$
            SELECT d.tenant_id FROM public.portal_domains d
             WHERE d.hostname = lower(p_host) AND d.status = 'active'
        $$
        """
    )
    # One answer for every bad link (no oracle): unknown, another firm's, used, revoked, expired.
    # A live link and the address it was sent to use it; another address leaves it unused.
    op.execute(
        """
        CREATE FUNCTION portal_link_claim(p_host text, p_token_sha256 text, p_email text)
        RETURNS text
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp
        SET statement_timeout = '5s' AS $$
        DECLARE
            v_previous text := current_setting('app.tenant_id', true);
            v_firm uuid;
            v_link record;
            v_outcome text := 'bad';
        BEGIN
            SELECT d.tenant_id INTO v_firm FROM public.portal_domains d
             WHERE d.hostname = lower(p_host) AND d.status = 'active';
            IF v_firm IS NULL OR p_token_sha256 IS NULL THEN
                RETURN 'bad';
            END IF;
            PERFORM set_config('app.tenant_id', v_firm::text, true);
            SELECT * INTO v_link FROM public.secure_links l
             WHERE l.token_sha256 = p_token_sha256 AND l.tenant_id = v_firm FOR UPDATE;
            IF FOUND AND v_link.used_at IS NULL AND v_link.revoked_at IS NULL
               AND v_link.expires_at > clock_timestamp() THEN
                IF v_link.recipient_email = lower(trim(p_email)) THEN
                    UPDATE public.secure_links SET used_at = clock_timestamp()
                     WHERE id = v_link.id;
                    v_outcome := 'claimed';
                ELSE
                    v_outcome := 'other';
                END IF;
            END IF;
            PERFORM set_config('app.tenant_id', coalesce(v_previous, ''), true);
            RETURN v_outcome;
        END $$
        """
    )
    # A recipient's renewal: a fresh row for the same contact, purpose, target and address, with
    # no token until delivery. Any link of the host's firm qualifies (expired or used: the person
    # still needs a way in) unless revoked or already renewed `p_per_hour` times in the last hour.
    op.execute(
        """
        CREATE FUNCTION portal_link_renew(
            p_host text, p_token_sha256 text, p_per_hour integer, p_days integer
        ) RETURNS TABLE (tenant_id uuid, link_id uuid, renewed_from_id uuid)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp
        SET statement_timeout = '5s' AS $$
        #variable_conflict use_column
        DECLARE
            v_previous text := current_setting('app.tenant_id', true);
            v_firm uuid;
            v_link record;
            v_recent integer;
            v_id uuid;
        BEGIN
            SELECT d.tenant_id INTO v_firm FROM public.portal_domains d
             WHERE d.hostname = lower(p_host) AND d.status = 'active';
            IF v_firm IS NULL OR p_token_sha256 IS NULL THEN
                RETURN;
            END IF;
            PERFORM set_config('app.tenant_id', v_firm::text, true);
            SELECT * INTO v_link FROM public.secure_links l
             WHERE l.token_sha256 = p_token_sha256 AND l.tenant_id = v_firm FOR UPDATE;
            IF FOUND AND v_link.revoked_at IS NULL THEN
                SELECT count(*) INTO v_recent FROM public.secure_links r
                 WHERE r.renewed_from_id = v_link.id
                   AND r.issued_at > clock_timestamp() - interval '1 hour';
                IF v_recent < p_per_hour THEN
                    INSERT INTO public.secure_links (tenant_id, contact_id, purpose,
                        target_kind, target_id, recipient_email, host, expires_at,
                        renewed_from_id)
                    VALUES (v_firm, v_link.contact_id, v_link.purpose, v_link.target_kind,
                        v_link.target_id, v_link.recipient_email, lower(p_host),
                        clock_timestamp() + make_interval(days => p_days), v_link.id)
                    RETURNING id INTO v_id;
                END IF;
            END IF;
            PERFORM set_config('app.tenant_id', coalesce(v_previous, ''), true);
            IF v_id IS NOT NULL THEN
                RETURN QUERY SELECT v_firm, v_id, v_link.id;
            END IF;
        END $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION portal_invitation_find(p_host text, p_token_sha256 text)
        RETURNS TABLE (tenant_id uuid, invitation_id uuid)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp
        SET statement_timeout = '5s' AS $$
            SELECT t.tenant_id, t.invitation_id FROM public.invitation_tokens t
              JOIN public.portal_domains d ON d.tenant_id = t.tenant_id
             WHERE t.token_hash = p_token_sha256 AND d.hostname = lower(p_host)
               AND d.status = 'active'
        $$
        """
    )
    # Story 7.2: the factor is the person's (one across firms, DEC-250), so removing it means the
    # next sign-in anywhere enrols again; the devices and sessions are this firm's.
    op.execute(
        """
        CREATE FUNCTION portal_mfa_reset(p_user_id uuid)
        RETURNS TABLE (kind text, ref text)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp
        SET statement_timeout = '5s' AS $$
        #variable_conflict use_column
        DECLARE
            v_tenant uuid := NULLIF(current_setting('app.tenant_id', true), '')::uuid;
        BEGIN
            IF v_tenant IS NULL THEN
                RAISE EXCEPTION 'no tenant';
            END IF;
            IF NOT EXISTS (SELECT 1 FROM public.memberships m
                            WHERE m.tenant_id = v_tenant AND m.user_id = p_user_id
                              AND m.kind = 'client') THEN
                RETURN;  -- not a client of this firm: nothing to reset
            END IF;
            RETURN QUERY
            WITH factor AS (
                DELETE FROM public.mfa_factors f WHERE f.user_id = p_user_id
                RETURNING f.factor_ref, f.enrolled_at
            ), codes AS (
                DELETE FROM public.mfa_backup_codes b WHERE b.user_id = p_user_id
                RETURNING b.id
            ), devices AS (
                UPDATE public.trusted_devices d SET revoked_at = clock_timestamp(),
                    revoked_reason = 'mfa_reset'
                 WHERE d.user_id = p_user_id AND d.tenant_id = v_tenant AND d.revoked_at IS NULL
                RETURNING d.id
            ), ended AS (
                UPDATE public.auth_sessions s SET ended_at = clock_timestamp(),
                    end_reason = 'revoked'
                 WHERE s.user_id = p_user_id AND s.tenant_id = v_tenant
                   AND s.surface = 'portal' AND s.ended_at IS NULL
                RETURNING s.id
            )
            SELECT CASE WHEN factor.enrolled_at IS NULL THEN 'pending_factor' ELSE 'factor' END,
                   factor.factor_ref FROM factor
            UNION ALL SELECT 'backup_code', codes.id::text FROM codes
            UNION ALL SELECT 'device', devices.id::text FROM devices
            UNION ALL SELECT 'session', ended.id::text FROM ended;
        END $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION portal_mfa_unlock(p_user_id uuid) RETURNS boolean
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp
        SET statement_timeout = '5s' AS $$
        DECLARE
            v_tenant uuid := NULLIF(current_setting('app.tenant_id', true), '')::uuid;
        BEGIN
            IF v_tenant IS NULL THEN
                RAISE EXCEPTION 'no tenant';
            END IF;
            IF NOT EXISTS (SELECT 1 FROM public.memberships m
                            WHERE m.tenant_id = v_tenant AND m.user_id = p_user_id
                              AND m.kind = 'client') THEN
                RETURN false;  -- not a client of this firm
            END IF;
            UPDATE public.mfa_factors SET mfa_attempts = 0, mfa_window_until = NULL,
                mfa_locked_until = NULL
             WHERE user_id = p_user_id AND mfa_locked_until > clock_timestamp();
            RETURN FOUND;
        END $$
        """
    )
    for function in _FUNCTIONS:
        op.execute(f"REVOKE ALL ON FUNCTION {function} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {function} TO abacus_app")

    _controls_check("platform_control_changes", _CONTROLS_HISTORY)
    _controls_check("platform_controls", _CONTROLS_HISTORY)
    op.execute(
        "UPDATE platform_controls SET control = 'portal_sign_in' "
        "WHERE control = 'portal_sign_in_disabled'"
    )
    _controls_check("platform_controls", _CONTROLS_V2)


def downgrade() -> None:
    _controls_check("platform_controls", _CONTROLS_HISTORY)
    op.execute(
        "UPDATE platform_controls SET control = 'portal_sign_in_disabled' "
        "WHERE control = 'portal_sign_in'"
    )
    _controls_check("platform_controls", _CONTROLS_V1)
    # The history keeps both spellings once a `portal_sign_in` row exists; it is insert-only.
    for function in reversed(_FUNCTIONS):
        op.execute(f"DROP FUNCTION {function}")
    op.execute("REVOKE UPDATE (renewal_count) ON client_invitations FROM abacus_app")
    op.execute("DROP TABLE secure_links")
