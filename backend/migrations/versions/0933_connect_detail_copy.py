"""The Connect catalogue's WB-11 detail copy (W-01 WB-11 rest; SPEC-659 AC-20 to AC-23; DEC-5337).

`integration_catalog.detail_copy` (jsonb object, catalogue content loaded by the reviewed import,
never typed in code): `writes` (each declared write's `label` and `gate_label`, joined with the
write-capability registry by its `key`), `never` (the lines Accrued never does), `who_can_use`
and `who_can_use_note`. `integration_catalog_workbench()` answers it; the import compares and
writes it like every other catalogue column.

Revision ID: 0933
Revises: 0932
"""

from __future__ import annotations

from alembic import op

revision = "0933"
down_revision = "0932"
branch_labels = None
depends_on = None

_GRANT = "GRANT EXECUTE ON FUNCTION integration_catalog_workbench() TO abacus_app, abacus_ops"


def upgrade() -> None:
    op.execute(
        "ALTER TABLE integration_catalog ADD COLUMN detail_copy jsonb NOT NULL "
        "DEFAULT '{}'::jsonb CHECK (jsonb_typeof(detail_copy) = 'object')"
    )
    op.execute("DROP FUNCTION integration_catalog_workbench()")
    op.execute(
        """
        CREATE FUNCTION integration_catalog_workbench() RETURNS TABLE (
            key text, name text, categories text[], ownership_mode text, surfaces text[],
            connector_provider text, adapter_key text, listing_status text, consent_copy jsonb,
            consent_version integer, scopes jsonb, icon text, tone text, sort_order integer,
            description text, auth_line text, published_at timestamptz, prerequisite jsonb,
            revision integer, detail_copy jsonb
        )
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
            SELECT c.key, c.name, c.categories, c.ownership_mode, c.surfaces,
                   c.connector_provider, c.adapter_key, c.listing_status, c.consent_copy,
                   c.consent_version, c.scopes, c.icon, c.tone, c.sort_order, c.description,
                   c.auth_line, c.published_at, c.prerequisite, c.revision, c.detail_copy
              FROM public.integration_catalog c
             WHERE 'workbench' = ANY (c.surfaces)
             ORDER BY c.sort_order, c.key
        $$
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION integration_catalog_import(
            p_rows jsonb, p_operator text, p_environment text, p_sha256 text, p_note text
        )
        RETURNS TABLE (import_id uuid, key text, change text)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        DECLARE
            r jsonb;
            v_old public.integration_catalog%ROWTYPE;
            v_new public.integration_catalog%ROWTYPE;
            v_id uuid := gen_random_uuid();
            v_keys text[] := '{}';
            v_added integer := 0;
            v_changed integer := 0;
            v_hidden integer := 0;
            v_key text;
        BEGIN
            IF jsonb_typeof(p_rows) <> 'array' THEN
                RAISE EXCEPTION 'rows is an array' USING ERRCODE = 'invalid_parameter_value';
            END IF;
            FOR r IN SELECT value FROM jsonb_array_elements(p_rows) LOOP
                v_new := jsonb_populate_record(NULL::public.integration_catalog, r);
                v_keys := v_keys || v_new.key;
                SELECT * INTO v_old FROM public.integration_catalog c
                 WHERE c.key = v_new.key FOR UPDATE;
                IF NOT FOUND THEN
                    INSERT INTO public.integration_catalog (key,
                        name, category, categories, ownership_mode, surfaces,
                        connector_provider, adapter_key, listing_status, consent_copy,
                        consent_version, scopes, icon, tone, sort_order, description, auth_line,
                        published_at, prerequisite, detail_copy,
                        content_sha256, import_id, loaded_by)
                    VALUES (v_new.key,
                        v_new.name, v_new.category, v_new.categories, v_new.ownership_mode,
                        v_new.surfaces, v_new.connector_provider, v_new.adapter_key,
                        v_new.listing_status, v_new.consent_copy, v_new.consent_version,
                        v_new.scopes, v_new.icon, v_new.tone, v_new.sort_order,
                        v_new.description, v_new.auth_line, v_new.published_at,
                        v_new.prerequisite, coalesce(v_new.detail_copy, '{}'::jsonb),
                        p_sha256, v_id, p_operator);
                    import_id := v_id; key := v_new.key; change := 'added'; RETURN NEXT;
                    v_added := v_added + 1;
                ELSIF (
                        v_old.name, v_old.category, v_old.categories, v_old.ownership_mode,
                        v_old.surfaces, v_old.connector_provider, v_old.adapter_key,
                        v_old.listing_status, v_old.consent_copy, v_old.consent_version,
                        v_old.scopes, v_old.icon, v_old.tone, v_old.sort_order,
                        v_old.description, v_old.auth_line, v_old.published_at,
                        v_old.prerequisite, v_old.detail_copy
                    ) IS DISTINCT FROM (
                        v_new.name, v_new.category, v_new.categories, v_new.ownership_mode,
                        v_new.surfaces, v_new.connector_provider, v_new.adapter_key,
                        v_new.listing_status, v_new.consent_copy, v_new.consent_version,
                        v_new.scopes, v_new.icon, v_new.tone, v_new.sort_order,
                        v_new.description, v_new.auth_line, v_new.published_at,
                        v_new.prerequisite, coalesce(v_new.detail_copy, '{}'::jsonb)
                    ) THEN
                    UPDATE public.integration_catalog c SET
                        name = v_new.name, category = v_new.category,
                        categories = v_new.categories, ownership_mode = v_new.ownership_mode,
                        surfaces = v_new.surfaces,
                        connector_provider = v_new.connector_provider,
                        adapter_key = v_new.adapter_key, listing_status = v_new.listing_status,
                        consent_copy = v_new.consent_copy,
                        consent_version = v_new.consent_version, scopes = v_new.scopes,
                        icon = v_new.icon, tone = v_new.tone, sort_order = v_new.sort_order,
                        description = v_new.description, auth_line = v_new.auth_line,
                        published_at = v_new.published_at, prerequisite = v_new.prerequisite,
                        detail_copy = coalesce(v_new.detail_copy, '{}'::jsonb),
                        revision = v_old.revision + 1, content_sha256 = p_sha256,
                        import_id = v_id, loaded_by = p_operator, loaded_at = clock_timestamp()
                     WHERE c.key = v_new.key;
                    import_id := v_id; key := v_new.key; change := 'changed'; RETURN NEXT;
                    v_changed := v_changed + 1;
                END IF;
            END LOOP;
            -- A workbench row the document no longer names leaves the tiles; never deleted.
            FOR v_key IN
                SELECT c.key FROM public.integration_catalog c
                 WHERE 'workbench' = ANY (c.surfaces) AND c.listing_status <> 'hidden'
                   AND NOT (c.key = ANY (v_keys))
                 FOR UPDATE
            LOOP
                UPDATE public.integration_catalog c SET listing_status = 'hidden',
                    revision = c.revision + 1, content_sha256 = p_sha256, import_id = v_id,
                    loaded_by = p_operator, loaded_at = clock_timestamp()
                 WHERE c.key = v_key;
                import_id := v_id; key := v_key; change := 'unpublished'; RETURN NEXT;
                v_hidden := v_hidden + 1;
            END LOOP;
            INSERT INTO public.integration_catalog_imports (id, operator, environment, dry_run,
                document_sha256, added, changed, unpublished, note)
            VALUES (v_id, p_operator, p_environment, false, p_sha256, v_added, v_changed,
                v_hidden, p_note);
        END
        $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION integration_catalog_workbench() FROM PUBLIC")
    op.execute(_GRANT)


def downgrade() -> None:
    op.execute("DROP FUNCTION integration_catalog_workbench()")
    op.execute(
        """
        CREATE FUNCTION integration_catalog_workbench() RETURNS TABLE (
            key text, name text, categories text[], ownership_mode text, surfaces text[],
            connector_provider text, adapter_key text, listing_status text, consent_copy jsonb,
            consent_version integer, scopes jsonb, icon text, tone text, sort_order integer,
            description text, auth_line text, published_at timestamptz, prerequisite jsonb,
            revision integer
        )
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
            SELECT c.key, c.name, c.categories, c.ownership_mode, c.surfaces,
                   c.connector_provider, c.adapter_key, c.listing_status, c.consent_copy,
                   c.consent_version, c.scopes, c.icon, c.tone, c.sort_order, c.description,
                   c.auth_line, c.published_at, c.prerequisite, c.revision
              FROM public.integration_catalog c
             WHERE 'workbench' = ANY (c.surfaces)
             ORDER BY c.sort_order, c.key
        $$
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION integration_catalog_import(
            p_rows jsonb, p_operator text, p_environment text, p_sha256 text, p_note text
        )
        RETURNS TABLE (import_id uuid, key text, change text)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        DECLARE
            r jsonb;
            v_old public.integration_catalog%ROWTYPE;
            v_new public.integration_catalog%ROWTYPE;
            v_id uuid := gen_random_uuid();
            v_keys text[] := '{}';
            v_added integer := 0;
            v_changed integer := 0;
            v_hidden integer := 0;
            v_key text;
        BEGIN
            IF jsonb_typeof(p_rows) <> 'array' THEN
                RAISE EXCEPTION 'rows is an array' USING ERRCODE = 'invalid_parameter_value';
            END IF;
            FOR r IN SELECT value FROM jsonb_array_elements(p_rows) LOOP
                v_new := jsonb_populate_record(NULL::public.integration_catalog, r);
                v_keys := v_keys || v_new.key;
                SELECT * INTO v_old FROM public.integration_catalog c
                 WHERE c.key = v_new.key FOR UPDATE;
                IF NOT FOUND THEN
                    INSERT INTO public.integration_catalog (key,
                        name, category, categories, ownership_mode, surfaces,
                        connector_provider, adapter_key, listing_status, consent_copy,
                        consent_version, scopes, icon, tone, sort_order, description, auth_line,
                        published_at, prerequisite,
                        content_sha256, import_id, loaded_by)
                    VALUES (v_new.key,
                        v_new.name, v_new.category, v_new.categories, v_new.ownership_mode,
                        v_new.surfaces, v_new.connector_provider, v_new.adapter_key,
                        v_new.listing_status, v_new.consent_copy, v_new.consent_version,
                        v_new.scopes, v_new.icon, v_new.tone, v_new.sort_order,
                        v_new.description, v_new.auth_line, v_new.published_at,
                        v_new.prerequisite,
                        p_sha256, v_id, p_operator);
                    import_id := v_id; key := v_new.key; change := 'added'; RETURN NEXT;
                    v_added := v_added + 1;
                ELSIF (
                        v_old.name, v_old.category, v_old.categories, v_old.ownership_mode,
                        v_old.surfaces, v_old.connector_provider, v_old.adapter_key,
                        v_old.listing_status, v_old.consent_copy, v_old.consent_version,
                        v_old.scopes, v_old.icon, v_old.tone, v_old.sort_order,
                        v_old.description, v_old.auth_line, v_old.published_at,
                        v_old.prerequisite
                    ) IS DISTINCT FROM (
                        v_new.name, v_new.category, v_new.categories, v_new.ownership_mode,
                        v_new.surfaces, v_new.connector_provider, v_new.adapter_key,
                        v_new.listing_status, v_new.consent_copy, v_new.consent_version,
                        v_new.scopes, v_new.icon, v_new.tone, v_new.sort_order,
                        v_new.description, v_new.auth_line, v_new.published_at,
                        v_new.prerequisite
                    ) THEN
                    UPDATE public.integration_catalog c SET
                        name = v_new.name, category = v_new.category,
                        categories = v_new.categories, ownership_mode = v_new.ownership_mode,
                        surfaces = v_new.surfaces,
                        connector_provider = v_new.connector_provider,
                        adapter_key = v_new.adapter_key, listing_status = v_new.listing_status,
                        consent_copy = v_new.consent_copy,
                        consent_version = v_new.consent_version, scopes = v_new.scopes,
                        icon = v_new.icon, tone = v_new.tone, sort_order = v_new.sort_order,
                        description = v_new.description, auth_line = v_new.auth_line,
                        published_at = v_new.published_at, prerequisite = v_new.prerequisite,
                        revision = v_old.revision + 1, content_sha256 = p_sha256,
                        import_id = v_id, loaded_by = p_operator, loaded_at = clock_timestamp()
                     WHERE c.key = v_new.key;
                    import_id := v_id; key := v_new.key; change := 'changed'; RETURN NEXT;
                    v_changed := v_changed + 1;
                END IF;
            END LOOP;
            -- A workbench row the document no longer names leaves the tiles; never deleted.
            FOR v_key IN
                SELECT c.key FROM public.integration_catalog c
                 WHERE 'workbench' = ANY (c.surfaces) AND c.listing_status <> 'hidden'
                   AND NOT (c.key = ANY (v_keys))
                 FOR UPDATE
            LOOP
                UPDATE public.integration_catalog c SET listing_status = 'hidden',
                    revision = c.revision + 1, content_sha256 = p_sha256, import_id = v_id,
                    loaded_by = p_operator, loaded_at = clock_timestamp()
                 WHERE c.key = v_key;
                import_id := v_id; key := v_key; change := 'unpublished'; RETURN NEXT;
                v_hidden := v_hidden + 1;
            END LOOP;
            INSERT INTO public.integration_catalog_imports (id, operator, environment, dry_run,
                document_sha256, added, changed, unpublished, note)
            VALUES (v_id, p_operator, p_environment, false, p_sha256, v_added, v_changed,
                v_hidden, p_note);
        END
        $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION integration_catalog_workbench() FROM PUBLIC")
    op.execute(_GRANT)
    op.execute("ALTER TABLE integration_catalog DROP COLUMN detail_copy")
