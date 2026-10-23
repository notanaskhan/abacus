"""Portal branding, portal hosts and portal preferences (P-08-T05; ADR-163, ADR-152).

- `portal_branding`: one row per firm, the slots POR-01 shows before sign-in. Every column a
  visitor can see is Public; `support_contact_user_id` is internal. The logo is stored here,
  already re-encoded as PNG by the app (metadata dropped, at most 256 KiB), with its SHA-256, so
  the same-origin logo route needs no bucket (DEC-154).
- `portal_domains`: the hosts a firm's portal answers on (`default` `<slug>.<neutral domain>`,
  `custom` from P1). Lower case and unique across firms, so it is global: a host has to be found
  before any tenant is known. The app has no grant on it; it adds and activates its own firm's
  hosts through `portal_domain_add` and `portal_domain_activate`, which bind the row to the
  transaction's tenant (DEC-154).
- `portal_preferences`: a portal user's per-scope choices (the dismissed welcome, POR-02b).

`portal_branding` and `portal_preferences` are tenant tables with forced RLS. Before sign-in there
is no tenant, so a host is resolved only through two SECURITY DEFINER lookups executable by the
app: `portal_resolve_host(host)` (the Public branding columns of the firm whose active host it is)
and `portal_host_logo(host)` (its logo). Each finds the host's firm, reads that firm's branding
under its own tenant setting (as 0032's sign-up does), and restores the caller's. Neither returns
a tenant id (ADR-163 §5, §6).

Revision ID: 0111
Revises: 0110
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0111"
down_revision = "0110"
branch_labels = None
depends_on = None

# Postgres caps a regex repetition at 255, so the length is its own check.
_HTTPS = "~ '^https://[^[:space:]]+$'"
_HOST = "~ '^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)+$'"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE portal_branding (
            tenant_id uuid PRIMARY KEY,
            display_name text NOT NULL CHECK (char_length(display_name) BETWEEN 1 AND 120),
            portal_name text NULL CHECK (char_length(portal_name) BETWEEN 1 AND 120),
            logo_png bytea NULL CHECK (octet_length(logo_png) BETWEEN 1 AND 262144),
            logo_sha256 bytea NULL CHECK (octet_length(logo_sha256) = 32),
            address_line text NULL CHECK (char_length(address_line) BETWEEN 1 AND 200),
            help_url text NULL CHECK (help_url {_HTTPS} AND char_length(help_url) <= 500),
            privacy_url text NULL CHECK (privacy_url {_HTTPS} AND char_length(privacy_url) <= 500),
            terms_url text NULL CHECK (terms_url {_HTTPS} AND char_length(terms_url) <= 500),
            terms_version integer NULL CHECK (terms_version >= 1),
            support_contact_user_id uuid NULL,
            support_contact_name text NULL
                CHECK (char_length(support_contact_name) BETWEEN 1 AND 120),
            secured_footer boolean NOT NULL DEFAULT false,
            maintenance_banner text NULL
                CHECK (char_length(maintenance_banner) BETWEEN 1 AND 280),
            version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
            updated_by uuid NOT NULL,
            updated_at timestamptz NOT NULL DEFAULT abacus_now(),
            CHECK ((logo_png IS NULL) = (logo_sha256 IS NULL)),
            FOREIGN KEY (tenant_id) REFERENCES firms (tenant_id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE portal_domains (
            hostname text PRIMARY KEY
                CHECK (hostname = lower(hostname) AND char_length(hostname) <= 253
                       AND hostname {_HOST}),
            tenant_id uuid NOT NULL REFERENCES firms (tenant_id),
            kind text NOT NULL CHECK (kind IN ('default', 'custom')),
            status text NOT NULL DEFAULT 'pending_dns'
                CHECK (status IN ('pending_dns', 'verifying', 'active', 'failed', 'disabled')),
            created_at timestamptz NOT NULL DEFAULT abacus_now(),
            verified_at timestamptz NULL
        )
        """
    )
    op.execute("CREATE INDEX portal_domains_tenant ON portal_domains (tenant_id)")
    op.execute("REVOKE ALL ON portal_domains FROM PUBLIC, abacus_app")
    op.execute(
        """
        CREATE TABLE portal_preferences (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES firms (tenant_id),
            user_id uuid NOT NULL,
            scope_kind text NOT NULL CHECK (scope_kind IN ('engagement', 'client', 'firm')),
            scope_id uuid NOT NULL,
            welcome_dismissed_at timestamptz NULL,
            version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
            updated_at timestamptz NOT NULL DEFAULT abacus_now(),
            UNIQUE (tenant_id, user_id, scope_kind, scope_id)
        )
        """
    )
    for table in ("portal_branding", "portal_preferences"):
        tenant_table(op, table)
        op.execute(f"REVOKE DELETE ON {table} FROM abacus_app")
    insert_columns(
        op,
        "portal_branding",
        (
            "tenant_id",
            "display_name",
            "portal_name",
            "logo_png",
            "logo_sha256",
            "address_line",
            "help_url",
            "privacy_url",
            "terms_url",
            "terms_version",
            "support_contact_user_id",
            "support_contact_name",
            "secured_footer",
            "maintenance_banner",
            "updated_by",
        ),
    )
    op.execute("REVOKE UPDATE ON portal_branding FROM abacus_app")
    op.execute(
        "GRANT UPDATE (display_name, portal_name, logo_png, logo_sha256, address_line, help_url, "
        "privacy_url, terms_url, terms_version, support_contact_user_id, support_contact_name, "
        "secured_footer, maintenance_banner, version, updated_by, updated_at) "
        "ON portal_branding TO abacus_app"
    )
    insert_columns(
        op,
        "portal_preferences",
        ("tenant_id", "user_id", "scope_kind", "scope_id", "welcome_dismissed_at"),
    )
    op.execute("REVOKE UPDATE ON portal_preferences FROM abacus_app")
    op.execute(
        "GRANT UPDATE (welcome_dismissed_at, version, updated_at) "
        "ON portal_preferences TO abacus_app"
    )

    # Each lookup finds the host's firm, then reads that firm's row under its tenant setting.
    lookup = """
        DECLARE
            v_tenant uuid;
            v_previous text := current_setting('app.tenant_id', true);
        BEGIN
            SELECT d.tenant_id INTO v_tenant FROM public.portal_domains d
             WHERE d.hostname = lower(p_host) AND d.status = 'active';
            IF v_tenant IS NULL THEN
                RETURN;
            END IF;
            PERFORM set_config('app.tenant_id', v_tenant::text, true);
            RETURN QUERY {select};
            PERFORM set_config('app.tenant_id', coalesce(v_previous, ''), true);
        END
    """
    op.execute(
        "CREATE FUNCTION portal_resolve_host(p_host text) "  # noqa: S608 -- fixed SQL, no input
        "RETURNS TABLE (display_name text, portal_name text, has_logo boolean, "
        "address_line text, help_url text, privacy_url text, support_contact_name text, "
        "secured_footer boolean, maintenance_banner text) "
        "LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$"
        + lookup.format(
            select="SELECT b.display_name, b.portal_name, b.logo_png IS NOT NULL, "
            "b.address_line, b.help_url, b.privacy_url, b.support_contact_name, "
            "b.secured_footer, b.maintenance_banner FROM public.portal_branding b "
            "WHERE b.tenant_id = v_tenant"
        )
        + "$$"
    )
    op.execute(
        "CREATE FUNCTION portal_host_logo(p_host text) RETURNS TABLE (logo_png bytea) "  # noqa: S608 -- fixed SQL
        "LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$"
        + lookup.format(
            select="SELECT b.logo_png FROM public.portal_branding b "
            "WHERE b.tenant_id = v_tenant AND b.logo_png IS NOT NULL"
        )
        + "$$"
    )
    # The app's own firm's hosts, bound to the transaction's tenant.
    op.execute(
        """
        CREATE FUNCTION portal_domain_add(p_host text, p_kind text) RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        DECLARE
            v_tenant uuid := NULLIF(current_setting('app.tenant_id', true), '')::uuid;
        BEGIN
            IF v_tenant IS NULL THEN
                RAISE EXCEPTION 'no tenant' USING ERRCODE = 'insufficient_privilege';
            END IF;
            INSERT INTO public.portal_domains (hostname, tenant_id, kind)
            VALUES (lower(p_host), v_tenant, p_kind);
        END $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION portal_domain_activate(p_host text) RETURNS boolean
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        DECLARE
            v_tenant uuid := NULLIF(current_setting('app.tenant_id', true), '')::uuid;
        BEGIN
            UPDATE public.portal_domains SET status = 'active', verified_at = abacus_now()
             WHERE hostname = lower(p_host) AND tenant_id = v_tenant;
            RETURN FOUND;
        END $$
        """
    )
    for signature in (
        "portal_resolve_host(text)",
        "portal_host_logo(text)",
        "portal_domain_add(text, text)",
        "portal_domain_activate(text)",
    ):
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO abacus_app")


def downgrade() -> None:
    op.execute("DROP FUNCTION portal_domain_activate(text)")
    op.execute("DROP FUNCTION portal_domain_add(text, text)")
    op.execute("DROP FUNCTION portal_host_logo(text)")
    op.execute("DROP FUNCTION portal_resolve_host(text)")
    op.execute("DROP TABLE portal_preferences")
    op.execute("DROP TABLE portal_domains")
    op.execute("DROP TABLE portal_branding")
