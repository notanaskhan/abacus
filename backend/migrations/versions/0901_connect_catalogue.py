"""W-01-T07 (S46; TASK-8098; ADR-150, P-17; SPEC-659 AC-1 to AC-5, AC-31 to AC-33; red): the
Connect catalogue's readers and its v2 import, expand-only.

- `integration_catalog.category` (C20 v1's portal category) may be NULL on a row the portal never
  lists: a workbench tile is tagged by `categories` (0890). A portal row still names one.
- `integration_catalog.prerequisite` (content): a tile that needs another integration's scope
  first, `{key, scope, reason}` (WB-10 a: Workstream needs CCH Axcess's Workstream scope); the
  service compares it with the firm's granted scopes and shows the reason, never a constant.
- `integration_catalog_workbench()`: the workbench columns (0890's `categories`, `description`,
  `auth_line`, `published_at`) beside the v1 ones, for the app (the table stays definer-only).
- `integration_catalog_import(rows, operator, environment, sha256, note)` (`abacus_ops` only): the
  reviewed v2 document applied in one transaction. A new key is added at revision 1; a row whose
  content differs is changed and its revision bumped; a workbench row the document no longer
  names is taken off the tiles (`listing_status = 'hidden'`); nothing is deleted. One
  `integration_catalog_imports` row records it. A dry run never reaches the database: the plan is
  pure (`integrations.catalog_import.plan_import`) and compares the same columns.

The availability fan-out (AC-33) needs no definer: `integration_interest` forces row-level
security, so it runs firm by firm inside each firm's own session (`notified_at`, 0890's grant).

Revision ID: 0901
Revises: 0900
"""

from __future__ import annotations

from alembic import op

revision = "0901"
down_revision = "0900"
branch_labels = None
depends_on = None

# The import compares and writes every catalogue column but the revision and the load facts
# (`integrations.catalog_import.COMPARED` lists the same ones).


def upgrade() -> None:
    op.execute("ALTER TABLE integration_catalog ALTER COLUMN category DROP NOT NULL")
    op.execute(
        "ALTER TABLE integration_catalog ADD CONSTRAINT integration_catalog_portal_category "
        "CHECK (category IS NOT NULL OR NOT ('portal' = ANY (surfaces)))"
    )
    op.execute(
        """
        ALTER TABLE integration_catalog ADD COLUMN prerequisite jsonb NULL
            CONSTRAINT integration_catalog_prerequisite CHECK (prerequisite IS NULL OR (
                jsonb_typeof(prerequisite) = 'object'
                AND jsonb_typeof(prerequisite -> 'key') = 'string'
                AND jsonb_typeof(prerequisite -> 'scope') = 'string'
                AND jsonb_typeof(prerequisite -> 'reason') = 'string'
                AND length(prerequisite ->> 'reason') <= 240
                AND (prerequisite - 'key' - 'scope' - 'reason') = '{}'::jsonb))
        """
    )
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
        CREATE FUNCTION integration_catalog_import(
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
    op.execute(
        """
        CREATE FUNCTION integration_catalog_import_log() RETURNS TABLE (
            id uuid, operator text, environment text, document_sha256 text, added integer,
            changed integer, unpublished integer, note text, created_at timestamptz
        )
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
            SELECT i.id, i.operator, i.environment, i.document_sha256, i.added, i.changed,
                   i.unpublished, i.note, i.created_at
              FROM public.integration_catalog_imports i
             ORDER BY i.created_at DESC, i.id
             LIMIT 50
        $$
        """
    )
    for function in (
        "integration_catalog_workbench()",
        "integration_catalog_import(jsonb, text, text, text, text)",
        "integration_catalog_import_log()",
    ):
        op.execute(f"REVOKE ALL ON FUNCTION {function} FROM PUBLIC")
    op.execute(
        "GRANT EXECUTE ON FUNCTION integration_catalog_workbench() TO abacus_app, abacus_ops"
    )
    for function in (
        "integration_catalog_import(jsonb, text, text, text, text)",
        "integration_catalog_import_log()",
    ):
        op.execute(f"GRANT EXECUTE ON FUNCTION {function} TO abacus_ops")
    # The import and its log now run through the definers above, so the operator role keeps no
    # direct privilege on the log (Q-01-T52: `abacus_ops` holds no table privilege; 0890 granted
    # SELECT, INSERT for the v1 path these definers replace).
    op.execute("REVOKE ALL ON integration_catalog_imports FROM abacus_ops")


def downgrade() -> None:
    op.execute("GRANT SELECT, INSERT ON integration_catalog_imports TO abacus_ops")
    op.execute("DROP FUNCTION integration_catalog_import_log()")
    op.execute("DROP FUNCTION integration_catalog_import(jsonb, text, text, text, text)")
    op.execute("DROP FUNCTION integration_catalog_workbench()")
    op.execute("ALTER TABLE integration_catalog DROP COLUMN prerequisite")
    op.execute(
        "ALTER TABLE integration_catalog DROP CONSTRAINT integration_catalog_portal_category"
    )
    # Refused by Postgres while a workbench-only row has no v1 category: such rows were loaded
    # by this revision's import and are hidden by hand first (rows are never deleted).
    op.execute("ALTER TABLE integration_catalog ALTER COLUMN category SET NOT NULL")
