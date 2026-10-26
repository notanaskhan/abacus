"""Firm email template versions, drafts and templated messages (R-01-T19; R-01 §4.2; DEC-449).

Extends P-01-T05's `email_templates` and `email_template_versions` (0092):

- `email_templates`: a row with `tenant_id` set is a firm's override of a key, created on the
  firm's first edit or import; `tenant_id` NULL stays the platform default. Keys may now have no
  dot (`reminder`). `firm_editable` and `audience` come from the key's registration.
  `UNIQUE (tenant_id, id)` lets a draft name only its own firm's row.
- `email_template_versions`: `format` `text` (0092's subject and body) or `blocks` (R-01's
  editor: subject, preheader, typed blocks, one call to action and its target, and the version's
  `source`). A platform block version keeps its wording in clear; a firm's keeps it only in
  `sealed` (AES-GCM under the firm's key, bound to the template, the version and the content
  hash), because it quotes the firm's own wording. Still insert-only for every role (0092's
  trigger); publishing writes version n+1 and moves `current_version_id`, so v3 stays readable
  after v4.
- **New** `email_template_drafts`: one draft per firm and template, sealed like a version;
  `draft_version` is the save's `expected_version`. The app inserts, updates the content columns
  and deletes (discard and publish).
- `messages` gains `template_version_id` and `kind` (`client`, `test`, `staff`).

The app holds no privilege on the two global tables. It reaches them through five SECURITY
DEFINER functions that take the firm from `app.tenant_id`, never from an argument:
`email_template_firm_row` (the firm's override row, created on first use),
`email_template_firm_id` (that row, if it exists),
`email_template_resolve` (the firm's current version, else the platform's),
`email_template_version_at` (a published version by number, the firm's first) and
`email_template_publish` (insert-only n+1 for the firm). No template text is written here
(AGENTS 16): firm content arrives through the editor or the import.

Revision ID: 0196
Revises: 0182
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0196"
down_revision = "0182"
branch_labels = None
depends_on = None

_TENANT = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"
_TARGETS = (
    "'portal_home', 'documents', 'request', 'room', 'sign', 'deliverables', 'confirm', "
    "'connections'"
)
_ROW = "email_template_firm_row(text, text)"
_FIRM_ID = "email_template_firm_id(text, text)"
_RESOLVE = "email_template_resolve(text, text)"
_AT = "email_template_version_at(text, text, integer)"
_PUBLISH = "email_template_publish(uuid, integer, bytea, text, text, text)"
_GUARD = "messages_sender_guard()"
# R-01's six firm-editable keys and their audiences (template_keys.py); a later epic's key adds
# its row in its own migration.
_REGISTRATIONS = """
    (NULL, 'invitation', 'en-US', true, ARRAY['client', 'third_party']),
    (NULL, 'reminder', 'en-US', true, ARRAY['client', 'third_party']),
    (NULL, 'signature_request', 'en-US', true, ARRAY['client']),
    (NULL, 'deliverable_ready', 'en-US', true, ARRAY['client']),
    (NULL, 'confirmation_request', 'en-US', true, ARRAY['respondent']),
    (NULL, 'reconnect_request', 'en-US', true, ARRAY['client'])
"""
_EDITABLE = """
              JOIN public.email_templates p ON p.tenant_id IS NULL AND p.key = t.key
               AND p.locale = t.locale AND p.firm_editable
"""
_VERSION_COLUMNS = """
    template_id uuid, version_id uuid, version integer, firm boolean, format text,
    subject text, preheader text, blocks jsonb, sealed bytea, cta_label text, cta_target text,
    content_sha256 text, published_by text, published_at timestamptz
"""
_SELECT_VERSION = """
    SELECT t.id, v.id, v.version, t.tenant_id IS NOT NULL, v.format, v.subject, v.preheader,
           v.blocks, v.sealed, v.cta_label, v.cta_target, v.content_sha256, v.published_by,
           v.published_at
"""


def upgrade() -> None:
    # --- email_templates: firm override rows -------------------------------------------------
    op.execute("ALTER TABLE email_templates DROP CONSTRAINT email_templates_tenant_id_check")
    op.execute("ALTER TABLE email_templates DROP CONSTRAINT email_templates_key_check")
    op.execute(
        """
        ALTER TABLE email_templates
            ADD CONSTRAINT email_templates_key_check
                CHECK (key ~ '^[a-z][a-z0-9_]*(\\.[a-z][a-z0-9_]*)*$' AND length(key) <= 100),
            ADD CONSTRAINT email_templates_tenant_fkey
                FOREIGN KEY (tenant_id) REFERENCES firms (tenant_id),
            ADD COLUMN firm_editable boolean NOT NULL DEFAULT false,
            ADD COLUMN audience text[] NOT NULL DEFAULT '{}'
                CHECK (audience <@ ARRAY['client', 'third_party', 'respondent', 'staff']),
            ADD CONSTRAINT email_templates_firm_rows_editable
                CHECK (tenant_id IS NULL OR firm_editable),
            ADD CONSTRAINT email_templates_tenant_id_id UNIQUE (tenant_id, id)
        """
    )
    # --- email_template_versions: the block format -------------------------------------------
    op.execute(
        f"""
        ALTER TABLE email_template_versions
            ALTER COLUMN subject DROP NOT NULL,
            ALTER COLUMN body_text DROP NOT NULL,
            ALTER COLUMN variables SET DEFAULT '{{}}',
            ADD COLUMN format text NOT NULL DEFAULT 'text' CHECK (format IN ('text', 'blocks')),
            ADD COLUMN preheader text NULL CHECK (length(preheader) <= 200),
            ADD COLUMN blocks jsonb NULL
                CHECK (jsonb_typeof(blocks) = 'array' AND jsonb_array_length(blocks) <= 40
                       AND octet_length(blocks::text) <= 100000),
            ADD COLUMN sealed bytea NULL CHECK (octet_length(sealed) <= 200000),
            ADD COLUMN cta_label text NULL CHECK (length(cta_label) BETWEEN 1 AND 60),
            ADD COLUMN cta_target text NULL CHECK (cta_target IN ({_TARGETS})),
            ADD COLUMN source text NOT NULL DEFAULT 'import'
                CHECK (source IN ('handoff_seed', 'editor', 'import')),
            ADD CONSTRAINT email_template_versions_shape CHECK (
                (format = 'text' AND subject IS NOT NULL AND body_text IS NOT NULL
                    AND blocks IS NULL AND sealed IS NULL AND preheader IS NULL
                    AND cta_label IS NULL AND cta_target IS NULL)
                OR (format = 'blocks' AND body_text IS NULL AND sealed IS NULL
                    AND subject IS NOT NULL AND preheader IS NOT NULL AND blocks IS NOT NULL)
                OR (format = 'blocks' AND body_text IS NULL AND sealed IS NOT NULL
                    AND subject IS NULL AND preheader IS NULL AND blocks IS NULL
                    AND cta_label IS NULL)
            ),
            ADD CONSTRAINT email_template_versions_cta_pair
                CHECK (cta_label IS NULL OR cta_target IS NOT NULL)
        """
    )
    # --- email_template_drafts ----------------------------------------------------------------
    op.execute(
        f"""
        CREATE TABLE email_template_drafts (
            tenant_id uuid NOT NULL,
            template_id uuid NOT NULL,
            base_version_id uuid NULL REFERENCES email_template_versions (id),
            sealed bytea NOT NULL CHECK (octet_length(sealed) BETWEEN 1 AND 200000),
            cta_target text NULL CHECK (cta_target IN ({_TARGETS})),
            draft_version integer NOT NULL CHECK (draft_version >= 1),
            updated_by uuid NOT NULL,
            updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            PRIMARY KEY (tenant_id, template_id),
            FOREIGN KEY (tenant_id, template_id) REFERENCES email_templates (tenant_id, id),
            FOREIGN KEY (tenant_id, updated_by) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    tenant_table(op, "email_template_drafts")
    op.execute("REVOKE UPDATE ON email_template_drafts FROM abacus_app")
    insert_columns(
        op,
        "email_template_drafts",
        (
            "tenant_id",
            "template_id",
            "base_version_id",
            "sealed",
            "cta_target",
            "draft_version",
            "updated_by",
        ),
    )
    op.execute(
        "GRANT UPDATE (base_version_id, sealed, cta_target, draft_version, updated_by, "
        "updated_at) ON email_template_drafts TO abacus_app"
    )
    # --- messages: which version a templated message used ------------------------------------
    op.execute(
        """
        ALTER TABLE messages
            ADD COLUMN template_version_id uuid NULL REFERENCES email_template_versions (id),
            ADD COLUMN kind text NULL CHECK (kind IN ('client', 'test', 'staff'))
        """
    )
    op.execute("GRANT INSERT (template_version_id, kind) ON messages TO abacus_app")
    # --- the firm-editable keys (registrations, not content; R-01 §4.7) ----------------------
    # The allowlist lives here, not only in code (security review M1): a firm may override only
    # a key whose platform row says `firm_editable`, with that row's audience. No text.
    op.execute(
        f"""
        INSERT INTO email_templates (tenant_id, key, locale, firm_editable, audience)
        VALUES {_REGISTRATIONS}
        ON CONFLICT DO NOTHING
        """  # noqa: S608 -- fixed SQL
    )
    # --- definer functions -------------------------------------------------------------------
    op.execute(
        f"""
        CREATE FUNCTION email_template_firm_row(p_key text, p_locale text)
        RETURNS uuid
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp
        SET statement_timeout = '5s'
        AS $$
        DECLARE
            v_tenant uuid := {_TENANT};
            v_audience text[];
            v_id uuid;
        BEGIN
            IF v_tenant IS NULL THEN
                RAISE EXCEPTION 'email_template_firm_row: no firm'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            SELECT p.audience INTO v_audience FROM public.email_templates p
             WHERE p.tenant_id IS NULL AND p.key = p_key AND p.locale = p_locale
               AND p.firm_editable;
            IF v_audience IS NULL THEN
                RAISE EXCEPTION 'email_template_firm_row: not a firm-editable key'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            INSERT INTO public.email_templates (tenant_id, key, locale, firm_editable, audience)
            VALUES (v_tenant, p_key, p_locale, true, v_audience)
            ON CONFLICT DO NOTHING;
            SELECT t.id INTO v_id FROM public.email_templates t
             WHERE t.tenant_id = v_tenant AND t.key = p_key AND t.locale = p_locale;
            RETURN v_id;
        END $$
        """,  # noqa: S608 -- fixed SQL; the tenant comes from the session
    )
    op.execute(
        f"""
        CREATE FUNCTION email_template_firm_id(p_key text, p_locale text) RETURNS uuid
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp
        AS $$
            SELECT t.id FROM public.email_templates t
             WHERE t.tenant_id = {_TENANT} AND t.key = p_key AND t.locale = p_locale
        $$
        """,  # noqa: S608 -- fixed SQL; the tenant comes from the session
    )
    op.execute(
        f"""
        CREATE FUNCTION email_template_resolve(p_key text, p_locale text)
        RETURNS TABLE ({_VERSION_COLUMNS})
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp
        AS $$
            {_SELECT_VERSION}
              FROM public.email_templates t
              JOIN public.email_template_versions v ON v.id = t.current_version_id
              {_EDITABLE}
             WHERE t.key = p_key AND t.locale = p_locale
               AND (t.tenant_id IS NULL OR t.tenant_id = {_TENANT})
             ORDER BY t.tenant_id IS NULL
             LIMIT 1
        $$
        """
    )
    op.execute(
        f"""
        CREATE FUNCTION email_template_version_at(p_key text, p_locale text, p_version integer)
        RETURNS TABLE ({_VERSION_COLUMNS})
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp
        AS $$
            {_SELECT_VERSION}
              FROM public.email_templates t
              JOIN public.email_template_versions v ON v.template_id = t.id
              {_EDITABLE}
             WHERE t.key = p_key AND t.locale = p_locale AND v.version = p_version
               AND (t.tenant_id IS NULL OR t.tenant_id = {_TENANT})
             ORDER BY t.tenant_id IS NULL
             LIMIT 1
        $$
        """
    )
    op.execute(
        f"""
        CREATE FUNCTION email_template_publish(
            p_template uuid, p_version integer, p_sealed bytea, p_cta_target text,
            p_sha text, p_source text
        ) RETURNS uuid
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp
        SET statement_timeout = '5s'
        AS $$
        DECLARE
            v_tenant uuid := {_TENANT};
            v_actor text := NULLIF(current_setting('app.actor_id', true), '');
            v_key text;
            v_locale text;
            v_current integer;
            v_id uuid;
        BEGIN
            -- Security review M1: a person publishes, as themself; the session says who.
            IF current_setting('app.actor_kind', true) IS DISTINCT FROM 'human'
               OR v_actor IS NULL OR v_actor !~ '^[0-9a-f-]{{36}}$' THEN
                RAISE EXCEPTION 'email_template_publish: a person publishes'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF p_source = 'handoff_seed' AND NOT EXISTS (
                SELECT 1 FROM public.firms f WHERE f.tenant_id = v_tenant AND f.synthetic
            ) THEN
                RAISE EXCEPTION 'email_template_publish: seed content only on a synthetic firm'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            SELECT t.key, t.locale INTO v_key, v_locale FROM public.email_templates t
             WHERE t.id = p_template AND t.tenant_id = v_tenant
               AND EXISTS (SELECT 1 FROM public.email_templates p WHERE p.tenant_id IS NULL
                           AND p.key = t.key AND p.locale = t.locale AND p.firm_editable)
               FOR UPDATE;
            IF v_key IS NULL OR v_tenant IS NULL THEN
                RAISE EXCEPTION 'email_template_publish: not this firm''s editable template'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            SELECT coalesce(max(v.version), 0) INTO v_current
              FROM public.email_template_versions v WHERE v.template_id = p_template;
            IF v_current = 0 THEN
                SELECT coalesce(max(v.version), 0) INTO v_current
                  FROM public.email_templates t
                  JOIN public.email_template_versions v ON v.id = t.current_version_id
                 WHERE t.tenant_id IS NULL AND t.key = v_key AND t.locale = v_locale;
            END IF;
            IF p_version <> v_current + 1 THEN
                RAISE EXCEPTION 'stale_version' USING ERRCODE = 'serialization_failure';
            END IF;
            INSERT INTO public.email_template_versions
                (template_id, version, format, sealed, cta_target, content_sha256,
                 published_by, source)
            VALUES (p_template, p_version, 'blocks', p_sealed, p_cta_target, p_sha,
                    'user:' || v_actor, p_source)
            RETURNING id INTO v_id;
            UPDATE public.email_templates SET current_version_id = v_id WHERE id = p_template;
            RETURN v_id;
        END $$
        """,  # noqa: S608 -- fixed SQL; the tenant and actor come from the session
    )
    # Security review M2, L3: who may record a templated message, and with whose version. A
    # templated message is a person's, or the system's scheduled Reminder from a version its own
    # firm published (DEC-74); an agent or policy never records any message (ADR-005); the
    # version is the platform's or the message's own firm's.
    op.execute(
        """
        CREATE FUNCTION messages_sender_guard() RETURNS trigger
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp
        AS $$
        DECLARE
            v_kind text := NULLIF(current_setting('app.actor_kind', true), '');
            v_owner uuid;
            v_key text;
            v_by text;
        BEGIN
            IF v_kind IN ('agent', 'policy') THEN
                RAISE EXCEPTION 'messages: an agent never sends'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF NEW.template_version_id IS NULL THEN
                RETURN NEW;
            END IF;
            SELECT t.tenant_id, t.key, v.published_by INTO v_owner, v_key, v_by
              FROM public.email_template_versions v
              JOIN public.email_templates t ON t.id = v.template_id
             WHERE v.id = NEW.template_version_id;
            IF v_owner IS NOT NULL AND v_owner <> NEW.tenant_id THEN
                RAISE EXCEPTION 'messages: another firm''s template version'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF v_kind = 'human' THEN
                RETURN NEW;
            END IF;
            IF v_kind = 'system' AND v_key = 'reminder' AND v_owner = NEW.tenant_id
               AND v_by LIKE 'user:%' AND NEW.created_by::text = substr(v_by, 6) THEN
                RETURN NEW;
            END IF;
            RAISE EXCEPTION 'messages: only a person, or the scheduled Reminder, sends a template'
                USING ERRCODE = 'insufficient_privilege';
        END $$
        """,
    )
    op.execute(
        "CREATE TRIGGER messages_sender_guard BEFORE INSERT ON messages "
        "FOR EACH ROW EXECUTE FUNCTION messages_sender_guard()"
    )
    for function in (_ROW, _FIRM_ID, _RESOLVE, _AT, _PUBLISH, _GUARD):
        op.execute(f"REVOKE ALL ON FUNCTION {function} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {function} TO abacus_app")


def downgrade() -> None:
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM email_templates WHERE tenant_id IS NOT NULL) "
        "OR EXISTS (SELECT 1 FROM email_templates WHERE tenant_id IS NULL AND firm_editable "
        "AND current_version_id IS NOT NULL) "
        "OR EXISTS (SELECT 1 FROM email_template_versions WHERE format <> 'text') "
        "OR EXISTS (SELECT 1 FROM messages WHERE template_version_id IS NOT NULL) THEN "
        "RAISE EXCEPTION 'refusing to downgrade: firm templates or block versions exist'; "
        "END IF; END $$"
    )
    op.execute("DROP TRIGGER messages_sender_guard ON messages")
    for function in (_GUARD, _PUBLISH, _AT, _RESOLVE, _FIRM_ID, _ROW):
        op.execute(f"DROP FUNCTION {function}")
    op.execute(
        "DELETE FROM email_templates WHERE tenant_id IS NULL AND firm_editable "
        "AND current_version_id IS NULL"
    )
    op.execute("ALTER TABLE messages DROP COLUMN kind, DROP COLUMN template_version_id")
    op.execute("DROP TABLE email_template_drafts")
    op.execute(
        """
        ALTER TABLE email_template_versions
            DROP CONSTRAINT email_template_versions_cta_pair,
            DROP CONSTRAINT email_template_versions_shape,
            DROP COLUMN source,
            DROP COLUMN cta_target,
            DROP COLUMN cta_label,
            DROP COLUMN sealed,
            DROP COLUMN blocks,
            DROP COLUMN preheader,
            DROP COLUMN format,
            ALTER COLUMN variables DROP DEFAULT,
            ALTER COLUMN body_text SET NOT NULL,
            ALTER COLUMN subject SET NOT NULL
        """
    )
    op.execute(
        """
        ALTER TABLE email_templates
            DROP CONSTRAINT email_templates_tenant_id_id,
            DROP CONSTRAINT email_templates_firm_rows_editable,
            DROP COLUMN audience,
            DROP COLUMN firm_editable,
            DROP CONSTRAINT email_templates_tenant_fkey,
            DROP CONSTRAINT email_templates_key_check,
            ADD CONSTRAINT email_templates_key_check
                CHECK (key ~ '^[a-z][a-z_]*(\\.[a-z][a-z_]*)+$'),
            ADD CONSTRAINT email_templates_tenant_id_check CHECK (tenant_id IS NULL)
        """
    )
