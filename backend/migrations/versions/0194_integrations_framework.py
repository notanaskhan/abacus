"""The integrations framework v1 (A-02-T12; TASK-1339; SPEC-333 AC-49, AC-50; ADR-136 / P-17,
ADR-040, ADR-035; DEC-438).

- `integration_catalog` (global, no tenant): one row per app a firm or a client may connect,
  with its category, ownership mode, surfaces, the `connections.provider` code it serves, the
  adapter key, its listing status, consent copy and read scopes. **Content, not code**: rows
  arrive only from a reviewed document through the operator's load (`abacus_tools.
  integration_catalog`), never from a migration or a seed (AGENTS 16). A row is never deleted;
  a change bumps its `revision`. The app holds no privilege on the table (schema_check's global
  rule); it reads through `integration_catalog_rows()`. Writes go through
  `integration_catalog_load(rows, operator)`, which only `abacus_ops` executes (the P-62
  reference-data pattern, as `retention_set_import`).
- `firm_integrations` (tenant): a firm's install of a catalogue app (T-01's CCH bridge, W-01's
  firm and personal apps); at most one live install per app (`status <> 'disconnected'`).
- `integration_secrets` (tenant, restricted): an install's credentials, sealed with the tenant's
  key with the install's id as associated data (ADR-035); never updated, deleted to crypto-erase.

Connectors only read (ADR-040): the catalogue's `scopes` carry `read` only (CHECK), and there is
no write column anywhere.

`down_revision` is 0193 on this branch (S10 wave B); the merge re-points the chain.

Revision ID: 0194
Revises: 0193
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0194"
down_revision = "0193"
branch_labels = None
depends_on = None

_KEY = "~ '^[a-z][a-z0-9_]{1,49}$'"
_CATEGORIES = "('ledger', 'bank_feed', 'card_feed', 'sales', 'payroll', 'hr', 'ticketing', 'grc')"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE integration_catalog (
            key text PRIMARY KEY CHECK (key {_KEY}),
            name text NOT NULL CHECK (length(name) BETWEEN 1 AND 80),
            category text NOT NULL CHECK (category IN {_CATEGORIES}),
            ownership_mode text NOT NULL
                CHECK (ownership_mode IN ('firm', 'personal', 'client_authorised')),
            surfaces text[] NOT NULL
                CHECK (cardinality(surfaces) > 0
                       AND surfaces <@ ARRAY['portal', 'workbench']::text[]),
            connector_provider text NULL UNIQUE CHECK (connector_provider {_KEY}),
            adapter_key text NULL CHECK (adapter_key {_KEY}),
            listing_status text NOT NULL
                CHECK (listing_status IN ('available', 'coming_soon', 'hidden')),
            consent_copy jsonb NULL CHECK (consent_copy IS NULL
                OR (jsonb_typeof(consent_copy) = 'object'
                    AND jsonb_typeof(consent_copy -> 'will') = 'array'
                    AND jsonb_typeof(consent_copy -> 'wont') = 'array'
                    AND jsonb_typeof(consent_copy -> 'authorization') = 'string')),
            consent_version integer NULL CHECK (consent_version >= 1),
            -- Read scopes only (ADR-040): a write scope has nowhere to go.
            scopes jsonb NOT NULL CHECK (
                jsonb_typeof(scopes) = 'object'
                AND jsonb_typeof(scopes -> 'read') = 'array'
                AND (scopes - 'read') = '{{}}'::jsonb
            ),
            icon text NOT NULL CHECK (icon ~ '^[a-z][a-z0-9-]{{0,39}}$'),
            tone text NOT NULL CHECK (tone IN ('olive', 'espresso', 'clay', 'ochre')),
            sort_order integer NOT NULL CHECK (sort_order >= 0),
            revision integer NOT NULL DEFAULT 1 CHECK (revision >= 1),
            loaded_by text NOT NULL CHECK (loaded_by ~ '^[a-z][a-z0-9._-]{{0,60}}$'),
            loaded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            CHECK ((consent_copy IS NULL) = (consent_version IS NULL)),
            -- A client-authorised app is a connection: it names the provider it serves.
            CHECK (ownership_mode <> 'client_authorised' OR connector_provider IS NOT NULL)
        )
        """
    )
    op.execute("REVOKE ALL ON integration_catalog FROM abacus_app")
    op.execute(
        """
        CREATE FUNCTION integration_catalog_rows() RETURNS TABLE (
            key text, name text, category text, ownership_mode text, surfaces text[],
            connector_provider text, adapter_key text, listing_status text, consent_copy jsonb,
            consent_version integer, scopes jsonb, icon text, tone text, sort_order integer,
            revision integer, loaded_at timestamptz
        )
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
            SELECT c.key, c.name, c.category, c.ownership_mode, c.surfaces,
                   c.connector_provider, c.adapter_key, c.listing_status, c.consent_copy,
                   c.consent_version, c.scopes, c.icon, c.tone, c.sort_order, c.revision,
                   c.loaded_at
              FROM public.integration_catalog c
             ORDER BY c.sort_order, c.key
        $$
        """
    )
    # The operator's load: every element of `p_rows` is one row (all columns but the revision
    # and the load facts). New keys are added at revision 1; a row whose content differs is
    # changed and its revision bumped; identical rows are left alone. Nothing is deleted.
    op.execute(
        """
        CREATE FUNCTION integration_catalog_load(p_rows jsonb, p_operator text)
        RETURNS TABLE (key text, change text)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        DECLARE
            r jsonb;
            v_old public.integration_catalog%ROWTYPE;
            v_new public.integration_catalog%ROWTYPE;
        BEGIN
            IF jsonb_typeof(p_rows) <> 'array' THEN
                RAISE EXCEPTION 'rows is an array' USING ERRCODE = 'invalid_parameter_value';
            END IF;
            FOR r IN SELECT value FROM jsonb_array_elements(p_rows) LOOP
                v_new := jsonb_populate_record(NULL::public.integration_catalog, r);
                SELECT * INTO v_old FROM public.integration_catalog c
                 WHERE c.key = v_new.key FOR UPDATE;
                IF NOT FOUND THEN
                    INSERT INTO public.integration_catalog (key, name, category,
                        ownership_mode, surfaces, connector_provider, adapter_key,
                        listing_status, consent_copy, consent_version, scopes, icon, tone,
                        sort_order, loaded_by)
                    VALUES (v_new.key, v_new.name, v_new.category, v_new.ownership_mode,
                        v_new.surfaces, v_new.connector_provider, v_new.adapter_key,
                        v_new.listing_status, v_new.consent_copy, v_new.consent_version,
                        v_new.scopes, v_new.icon, v_new.tone, v_new.sort_order, p_operator);
                    key := v_new.key; change := 'added';
                    RETURN NEXT;
                ELSIF (v_old.name, v_old.category, v_old.ownership_mode, v_old.surfaces,
                       v_old.connector_provider, v_old.adapter_key, v_old.listing_status,
                       v_old.consent_copy, v_old.consent_version, v_old.scopes, v_old.icon,
                       v_old.tone, v_old.sort_order)
                      IS DISTINCT FROM
                      (v_new.name, v_new.category, v_new.ownership_mode, v_new.surfaces,
                       v_new.connector_provider, v_new.adapter_key, v_new.listing_status,
                       v_new.consent_copy, v_new.consent_version, v_new.scopes, v_new.icon,
                       v_new.tone, v_new.sort_order) THEN
                    UPDATE public.integration_catalog c SET
                        name = v_new.name, category = v_new.category,
                        ownership_mode = v_new.ownership_mode, surfaces = v_new.surfaces,
                        connector_provider = v_new.connector_provider,
                        adapter_key = v_new.adapter_key, listing_status = v_new.listing_status,
                        consent_copy = v_new.consent_copy,
                        consent_version = v_new.consent_version, scopes = v_new.scopes,
                        icon = v_new.icon, tone = v_new.tone, sort_order = v_new.sort_order,
                        revision = v_old.revision + 1, loaded_by = p_operator,
                        loaded_at = clock_timestamp()
                     WHERE c.key = v_new.key;
                    key := v_new.key; change := 'changed';
                    RETURN NEXT;
                END IF;
            END LOOP;
        END
        $$
        """
    )
    for function in ("integration_catalog_rows()", "integration_catalog_load(jsonb, text)"):
        op.execute(f"REVOKE ALL ON FUNCTION {function} FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION integration_catalog_rows() TO abacus_app, abacus_ops")
    op.execute("GRANT EXECUTE ON FUNCTION integration_catalog_load(jsonb, text) TO abacus_ops")

    op.execute(
        """
        CREATE TABLE firm_integrations (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            catalog_key text NOT NULL REFERENCES integration_catalog (key),
            status text NOT NULL DEFAULT 'connected'
                CHECK (status IN ('connected', 'needs_attention', 'disconnected')),
            mode text NOT NULL CHECK (mode IN ('token', 'file_bridge')),
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT abacus_now(),
            version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, created_by) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX firm_integrations_one_live ON firm_integrations "
        "(tenant_id, catalog_key) WHERE status <> 'disconnected'"
    )
    tenant_table(op, "firm_integrations")
    op.execute("REVOKE UPDATE, DELETE ON firm_integrations FROM abacus_app")
    insert_columns(
        op, "firm_integrations", ("tenant_id", "catalog_key", "status", "mode", "created_by")
    )
    op.execute("GRANT UPDATE (status, version) ON firm_integrations TO abacus_app")

    op.execute(
        """
        CREATE TABLE integration_secrets (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            firm_integration_id uuid NOT NULL,
            sealed bytea NOT NULL CHECK (octet_length(sealed) BETWEEN 1 AND 65536),
            key_id text NOT NULL CHECK (length(key_id) BETWEEN 1 AND 300),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, firm_integration_id),
            FOREIGN KEY (tenant_id, firm_integration_id)
                REFERENCES firm_integrations (tenant_id, id)
        )
        """
    )
    tenant_table(op, "integration_secrets")
    # Never updated; deleting the row is the crypto-erase (the sealed blob is the only copy).
    op.execute("REVOKE UPDATE ON integration_secrets FROM abacus_app")
    insert_columns(
        op, "integration_secrets", ("tenant_id", "firm_integration_id", "sealed", "key_id")
    )


def downgrade() -> None:
    op.execute("DROP TABLE integration_secrets")
    op.execute("DROP TABLE firm_integrations")
    op.execute("DROP FUNCTION integration_catalog_load(jsonb, text)")
    op.execute("DROP FUNCTION integration_catalog_rows()")
    op.execute("DROP TABLE integration_catalog")
