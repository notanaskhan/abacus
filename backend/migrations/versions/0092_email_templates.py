"""Email templates, the C16 email half (P-01-T05).

- `email_templates`: one per (key, locale). `tenant_id` NULL is the platform default, the only
  kind for now (CHECK); R-01 adds per-firm overrides, branding and the editor. Unique on
  `(coalesce(tenant_id, zero), key, locale)`.
- `email_template_versions`: insert-only (no app privilege; a trigger refuses UPDATE, DELETE and
  TRUNCATE for every role). Each holds its subject, text body, declared variables and content
  hash. The template's `current_version_id` names the one in use.
- Both are global: the app reaches them only through two SECURITY DEFINER functions:
  - `email_template_import(...)`: the staff-issuer import route. It is idempotent on the content
    hash: importing the current content again returns the current version and writes nothing.
  - `email_template_current(key, locale)`: what the renderer reads.

Revision ID: 0092
Revises: 0091
"""

from __future__ import annotations

from alembic import op

revision = "0092"
down_revision = "0091"
branch_labels = None
depends_on = None

_IMPORT = "email_template_import(text, text, text, text, text[], text, text)"
_CURRENT = "email_template_current(text, text)"


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE email_templates (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NULL CHECK (tenant_id IS NULL),
            key text NOT NULL CHECK (key ~ '^[a-z][a-z_]*(\\.[a-z][a-z_]*)+$'),
            channel text NOT NULL DEFAULT 'email' CHECK (channel = 'email'),
            locale text NOT NULL DEFAULT 'en-US' CHECK (locale ~ '^[a-z]{2}-[A-Z]{2}$'),
            current_version_id uuid NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp()
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX email_templates_once ON email_templates "
        "(coalesce(tenant_id, '00000000-0000-0000-0000-000000000000'::uuid), key, locale)"
    )
    op.execute(
        """
        CREATE TABLE email_template_versions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            template_id uuid NOT NULL REFERENCES email_templates (id),
            version integer NOT NULL CHECK (version >= 1),
            subject text NOT NULL CHECK (length(subject) BETWEEN 1 AND 200),
            body_text text NOT NULL CHECK (length(body_text) BETWEEN 1 AND 20000),
            variables text[] NOT NULL,
            status text NOT NULL DEFAULT 'published'
                CHECK (status IN ('draft', 'published', 'retired')),
            content_sha256 text NOT NULL CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
            published_by text NOT NULL CHECK (length(published_by) BETWEEN 1 AND 200),
            published_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (template_id, version)
        )
        """
    )
    op.execute(
        "ALTER TABLE email_templates ADD CONSTRAINT email_templates_current_fkey "
        "FOREIGN KEY (current_version_id) REFERENCES email_template_versions (id)"
    )
    for table in ("email_templates", "email_template_versions"):
        op.execute(f"REVOKE ALL ON {table} FROM abacus_app, PUBLIC")
    op.execute(
        """
        CREATE FUNCTION email_template_versions_immutable() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'email template versions are insert-only'
                USING ERRCODE = 'insufficient_privilege';
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER email_template_versions_immutable BEFORE UPDATE OR DELETE "
        "ON email_template_versions FOR EACH ROW "
        "EXECUTE FUNCTION email_template_versions_immutable()"
    )
    op.execute(
        "CREATE TRIGGER email_template_versions_no_truncate BEFORE TRUNCATE "
        "ON email_template_versions FOR EACH STATEMENT "
        "EXECUTE FUNCTION email_template_versions_immutable()"
    )
    op.execute(
        """
        CREATE FUNCTION email_template_import(
            p_key text, p_locale text, p_subject text, p_body text, p_variables text[],
            p_sha text, p_by text
        ) RETURNS TABLE (template_id uuid, version integer, content_sha256 text, created boolean)
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp
        SET statement_timeout = '5s'
        AS $$
        #variable_conflict use_column
        DECLARE
            v_template uuid;
            v_current uuid;
            v_version integer;
            v_id uuid;
        BEGIN
            INSERT INTO public.email_templates (key, locale) VALUES (p_key, p_locale)
            ON CONFLICT DO NOTHING;
            SELECT t.id, t.current_version_id INTO v_template, v_current
              FROM public.email_templates t
             WHERE t.tenant_id IS NULL AND t.key = p_key AND t.locale = p_locale
               FOR UPDATE;
            IF v_current IS NOT NULL THEN
                SELECT v.version INTO v_version FROM public.email_template_versions v
                 WHERE v.id = v_current AND v.content_sha256 = p_sha;
                IF v_version IS NOT NULL THEN
                    RETURN QUERY SELECT v_template, v_version, p_sha, false;
                    RETURN;
                END IF;
            END IF;
            SELECT coalesce(max(v.version), 0) + 1 INTO v_version
              FROM public.email_template_versions v WHERE v.template_id = v_template;
            INSERT INTO public.email_template_versions
                (template_id, version, subject, body_text, variables, content_sha256, published_by)
            VALUES (v_template, v_version, p_subject, p_body, p_variables, p_sha, p_by)
            RETURNING id INTO v_id;
            UPDATE public.email_templates SET current_version_id = v_id WHERE id = v_template;
            RETURN QUERY SELECT v_template, v_version, p_sha, true;
        END $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION email_template_current(p_key text, p_locale text)
        RETURNS TABLE (template_id uuid, version integer, subject text, body_text text,
                       variables text[], content_sha256 text)
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp
        AS $$
            SELECT t.id, v.version, v.subject, v.body_text, v.variables, v.content_sha256
              FROM public.email_templates t
              JOIN public.email_template_versions v ON v.id = t.current_version_id
             WHERE t.tenant_id IS NULL AND t.key = p_key AND t.locale = p_locale
        $$
        """
    )
    for function in (_IMPORT, _CURRENT):
        op.execute(f"REVOKE ALL ON FUNCTION {function} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {function} TO abacus_app")


def downgrade() -> None:
    op.execute(f"DROP FUNCTION {_CURRENT}")
    op.execute(f"DROP FUNCTION {_IMPORT}")
    op.execute("ALTER TABLE email_templates DROP CONSTRAINT email_templates_current_fkey")
    op.execute("DROP TABLE email_template_versions")
    op.execute("DROP FUNCTION email_template_versions_immutable()")
    op.execute("DROP TABLE email_templates")
