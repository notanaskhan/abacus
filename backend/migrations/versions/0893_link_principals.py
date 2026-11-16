"""A-08-T15 (S46; TASK-8083; ADR-146 P-09; ADR-152 amendment; SPEC-657 F6, F7): `link_principals`,
expand-only, red.

A link principal is the one identity a public `/v1/confirm/{token}` page acts as: a firm mints it
for one purpose and one subject (a confirmation) and one address, and its token travels only in
the link. Nothing here trusts a header or a session.

- `link_principals`: tenant, purpose (`register_link_purpose`), subject, the SHA-256 of the token
  and of the address it was sent to, expiry, revocation, the lock after five wrong codes.
- `link_principal_challenges`: a 10-minute emailed code per request, only its salted digest kept,
  issued at delivery (communications), tries counted before comparing.
- `link_page_credentials`: after a verified code, the page credential (`__Host-` cookie) and its
  CSRF value, both as SHA-256, pinned to the principal and short-lived.

Definers (no tenant on the public path; each returns nothing for a token that is unknown, expired,
revoked or locked, so the caller answers them all the same): `link_principal_resolve`,
`link_principal_challenge`, `link_principal_issue`, `link_principal_attempt`,
`link_principal_credential`, `link_principal_credential_resolve`. Five wrong codes lock the link
for 15 minutes.

Revision ID: 0893
Revises: 0892
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0893"
down_revision = "0892"
branch_labels = None
depends_on = None

_SHA = "bytea NOT NULL CHECK (octet_length({c}) = 32)"
_FUNCTIONS = (
    "link_principal_resolve(bytea)",
    "link_principal_challenge(bytea, bytea, integer, integer)",
    "link_principal_issue(uuid, bytea, bytea)",
    "link_principal_attempt(bytea, integer, integer)",
    "link_principal_missed(uuid, uuid, integer, integer)",
    "link_principal_credential(uuid, uuid, bytea, bytea, integer)",
    "link_principal_credential_resolve(bytea, bytea)",
)


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE link_principals (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES firms (tenant_id),
            purpose text NOT NULL CHECK (purpose ~ '^[a-z][a-z_]{{0,39}}$'),
            subject_id uuid NOT NULL,
            token_sha256 {_SHA.format(c="token_sha256")} UNIQUE,
            email_sha256 {_SHA.format(c="email_sha256")},
            -- the address the code goes to, sealed (only communications opens it, at delivery)
            email_sealed bytea NOT NULL CHECK (octet_length(email_sealed) <= 4096),
            expires_at timestamptz NOT NULL,
            revoked_at timestamptz NULL,
            locked_until timestamptz NULL,
            failed_codes integer NOT NULL DEFAULT 0 CHECK (failed_codes >= 0),
            verified_at timestamptz NULL,
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            CHECK (expires_at > created_at)
        )
        """
    )
    tenant_table(op, "link_principals")
    # The definers (the table owner) resolve a token before any tenant is known: not FORCEd, so
    # the owner reads past RLS while the app role stays bound by the tenant policy.
    op.execute("ALTER TABLE link_principals NO FORCE ROW LEVEL SECURITY")
    op.execute("REVOKE UPDATE, DELETE, TRUNCATE ON link_principals FROM abacus_app")
    insert_columns(
        op,
        "link_principals",
        (
            "tenant_id",
            "purpose",
            "subject_id",
            "token_sha256",
            "email_sha256",
            "email_sealed",
            "expires_at",
            "created_by",
        ),
    )
    op.execute("GRANT UPDATE (revoked_at) ON link_principals TO abacus_app")
    op.execute(
        """
        CREATE TABLE link_principal_challenges (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            principal_id uuid NOT NULL,
            code_salt bytea NULL CHECK (octet_length(code_salt) = 16),
            code_digest bytea NULL CHECK (octet_length(code_digest) = 32),
            code_expires_at timestamptz NOT NULL,
            tries integer NOT NULL DEFAULT 0 CHECK (tries >= 0),
            consumed_at timestamptz NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            FOREIGN KEY (tenant_id, principal_id) REFERENCES link_principals (tenant_id, id)
        )
        """
    )
    tenant_table(op, "link_principal_challenges")
    # The definers (the table owner) resolve a token before any tenant is known: not FORCEd, so
    # the owner reads past RLS while the app role stays bound by the tenant policy.
    op.execute("ALTER TABLE link_principal_challenges NO FORCE ROW LEVEL SECURITY")
    op.execute("REVOKE ALL ON link_principal_challenges FROM abacus_app")
    op.execute(
        f"""
        CREATE TABLE link_page_credentials (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            principal_id uuid NOT NULL,
            credential_sha256 {_SHA.format(c="credential_sha256")} UNIQUE,
            csrf_sha256 {_SHA.format(c="csrf_sha256")},
            expires_at timestamptz NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            FOREIGN KEY (tenant_id, principal_id) REFERENCES link_principals (tenant_id, id)
        )
        """
    )
    tenant_table(op, "link_page_credentials")
    # The definers (the table owner) resolve a token before any tenant is known: not FORCEd, so
    # the owner reads past RLS while the app role stays bound by the tenant policy.
    op.execute("ALTER TABLE link_page_credentials NO FORCE ROW LEVEL SECURITY")
    op.execute("REVOKE ALL ON link_page_credentials FROM abacus_app")

    # The link as it stands: open only; anything else returns no row (uniform to the caller).
    op.execute(
        """
        CREATE FUNCTION link_principal_resolve(p_token bytea)
        RETURNS TABLE (tenant_id uuid, principal_id uuid, purpose text, subject_id uuid,
                       verified boolean)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
            SELECT l.tenant_id, l.id, l.purpose, l.subject_id, l.verified_at IS NOT NULL
              FROM public.link_principals l
             WHERE l.token_sha256 = p_token AND l.revoked_at IS NULL
               AND l.expires_at > clock_timestamp()
               AND (l.locked_until IS NULL OR l.locked_until <= clock_timestamp())
        $$
        """
    )
    # A code request: a challenge only when the typed address is the link's; never says which.
    op.execute(
        """
        CREATE FUNCTION link_principal_challenge(
            p_token bytea, p_email bytea, p_code_seconds integer, p_resend_seconds integer
        ) RETURNS TABLE (challenge_id uuid, tenant_id uuid)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        #variable_conflict use_column
        DECLARE v_link record;
        BEGIN
            SELECT l.* INTO v_link FROM public.link_principals l
             WHERE l.token_sha256 = p_token AND l.revoked_at IS NULL
               AND l.expires_at > clock_timestamp()
               AND (l.locked_until IS NULL OR l.locked_until <= clock_timestamp())
             FOR UPDATE;
            IF NOT FOUND OR v_link.email_sha256 <> p_email THEN
                RETURN;
            END IF;
            IF EXISTS (SELECT 1 FROM public.link_principal_challenges c
                        WHERE c.principal_id = v_link.id AND c.consumed_at IS NULL
                          AND c.created_at > clock_timestamp() - make_interval(secs =>
                          p_resend_seconds)) THEN
                RETURN;
            END IF;
            RETURN QUERY
            INSERT INTO public.link_principal_challenges (tenant_id, principal_id, code_expires_at)
            VALUES (v_link.tenant_id, v_link.id,
                    clock_timestamp() + make_interval(secs => p_code_seconds))
            RETURNING id, tenant_id;
        END $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION link_principal_issue(p_id uuid, p_salt bytea, p_digest bytea)
        RETURNS TABLE (tenant_id uuid, principal_id uuid, code_expires_at timestamptz,
                       email_sealed bytea)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        #variable_conflict use_column
        BEGIN
            RETURN QUERY
            UPDATE public.link_principal_challenges c SET code_salt = p_salt, code_digest =
            p_digest
              FROM public.link_principals l
             WHERE c.id = p_id AND l.id = c.principal_id AND c.code_digest IS NULL
               AND c.consumed_at IS NULL AND c.code_expires_at > clock_timestamp()
            RETURNING c.tenant_id, c.principal_id, c.code_expires_at, l.email_sealed;
        END $$
        """
    )
    # A guess is counted on the link before it is compared (five a lock window, then 15 minutes
    # locked); 'ok' hands back the digest for the caller's constant-time comparison.
    op.execute(
        """
        CREATE FUNCTION link_principal_attempt(p_token bytea, p_max integer, p_lock_seconds
        integer)
        RETURNS TABLE (outcome text, tenant_id uuid, principal_id uuid, challenge_id uuid,
                       code_salt bytea, code_digest bytea)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        #variable_conflict use_column
        DECLARE v_link record; v_challenge record;
        BEGIN
            SELECT l.* INTO v_link FROM public.link_principals l
             WHERE l.token_sha256 = p_token AND l.revoked_at IS NULL
               AND l.expires_at > clock_timestamp() FOR UPDATE;
            IF NOT FOUND THEN
                RETURN QUERY SELECT 'unknown'::text, NULL::uuid, NULL::uuid, NULL::uuid,
                NULL::bytea, NULL::bytea;
                RETURN;
            END IF;
            IF v_link.locked_until IS NOT NULL AND v_link.locked_until > clock_timestamp() THEN
                RETURN QUERY SELECT 'locked'::text, v_link.tenant_id, v_link.id, NULL::uuid,
                NULL::bytea, NULL::bytea;
                RETURN;
            END IF;
            SELECT c.* INTO v_challenge FROM public.link_principal_challenges c
             WHERE c.principal_id = v_link.id AND c.consumed_at IS NULL AND c.code_digest IS NOT
             NULL
               AND c.code_expires_at > clock_timestamp()
             ORDER BY c.created_at DESC LIMIT 1 FOR UPDATE;
            IF NOT FOUND THEN
                RETURN QUERY SELECT 'no_code'::text, v_link.tenant_id, v_link.id, NULL::uuid,
                NULL::bytea, NULL::bytea;
                RETURN;
            END IF;
            UPDATE public.link_principal_challenges SET tries = tries + 1 WHERE id =
            v_challenge.id;
            RETURN QUERY SELECT 'ok'::text, v_link.tenant_id, v_link.id, v_challenge.id,
                                v_challenge.code_salt, v_challenge.code_digest;
        END $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION link_principal_missed(
            p_principal uuid, p_challenge uuid, p_max integer, p_lock_seconds integer
        ) RETURNS TABLE (failed integer, locked_until timestamptz)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        #variable_conflict use_column
        BEGIN
            RETURN QUERY
            UPDATE public.link_principals l
               SET failed_codes = CASE WHEN l.failed_codes + 1 >= p_max THEN 0 ELSE l.failed_codes
               + 1 END,
                   locked_until = CASE WHEN l.failed_codes + 1 >= p_max
                                       THEN clock_timestamp() + make_interval(secs =>
                                       p_lock_seconds)
                                       ELSE l.locked_until END
             WHERE l.id = p_principal
            RETURNING l.failed_codes, l.locked_until;
            IF (SELECT locked_until FROM public.link_principals WHERE id = p_principal) >
            clock_timestamp() THEN
                UPDATE public.link_principal_challenges SET consumed_at = clock_timestamp()
                 WHERE principal_id = p_principal AND consumed_at IS NULL;
            END IF;
        END $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION link_principal_credential(
            p_principal uuid, p_challenge uuid, p_credential bytea, p_csrf bytea, p_seconds integer
        ) RETURNS TABLE (tenant_id uuid, expires_at timestamptz)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        #variable_conflict use_column
        BEGIN
            UPDATE public.link_principal_challenges SET consumed_at = clock_timestamp()
             WHERE id = p_challenge AND consumed_at IS NULL;
            UPDATE public.link_principals SET verified_at = coalesce(verified_at,
            clock_timestamp()),
                   failed_codes = 0 WHERE id = p_principal;
            RETURN QUERY
            INSERT INTO public.link_page_credentials (tenant_id, principal_id, credential_sha256,
                                                      csrf_sha256, expires_at)
            SELECT l.tenant_id, l.id, p_credential, p_csrf,
                   clock_timestamp() + make_interval(secs => p_seconds)
              FROM public.link_principals l WHERE l.id = p_principal
            RETURNING tenant_id, expires_at;
        END $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION link_principal_credential_resolve(p_credential bytea, p_csrf bytea)
        RETURNS TABLE (tenant_id uuid, principal_id uuid, purpose text, subject_id uuid)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
            SELECT l.tenant_id, l.id, l.purpose, l.subject_id
              FROM public.link_page_credentials c JOIN public.link_principals l ON l.id =
              c.principal_id
             WHERE c.credential_sha256 = p_credential AND c.csrf_sha256 = p_csrf
               AND c.expires_at > clock_timestamp() AND l.revoked_at IS NULL
               AND l.expires_at > clock_timestamp()
        $$
        """
    )
    for function in _FUNCTIONS:
        op.execute(f"REVOKE ALL ON FUNCTION {function} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {function} TO abacus_app")


def downgrade() -> None:
    for function in reversed(_FUNCTIONS):
        op.execute(f"DROP FUNCTION {function}")
    op.execute("DROP TABLE link_page_credentials")
    op.execute("DROP TABLE link_principal_challenges")
    op.execute("DROP TABLE link_principals")
