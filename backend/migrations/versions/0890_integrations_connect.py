"""W-01-T04 (S45; TASK-8062; ADR-150, P-17; SPEC-659 AC-4, AC-10 to AC-13, AC-24, AC-27, AC-31,
AC-32, AC-35; red): C20 v2 Connect, expand-only.

- `integration_catalog` (platform content) gains the workbench columns: `categories text[]` (the
  WB-10 codes), `description`, `auth_line`, `published_at` (a row lists only once the clock has
  passed it), `content_sha256` and `import_id`; its tone CHECK gains `brick` (CRM, Spend).
- `integration_catalog_imports` (platform, insert-only): each operator import, dry run or apply,
  with the document's SHA-256, the counts and the note.
- `firm_integrations` widens: status `connecting · connected · needs_attention · needs_reauth ·
  paused · disconnected`, mode `+ firm_app`, and the facts the drawer reads (reason code, status
  time, token renewal, last sync, granted scopes, consent version, who connected and when). A firm
  app has no creator of its own, so `created_by` may be NULL for `firm_app` rows only.
- **Backfill:** a `connected` firm-app row for every tenant and provider with a live client
  connection (reason `backfill`), so the flag-gated POR-16 check refuses nothing that works today.
  The migrator owns the tables but has no BYPASSRLS: FORCE is lifted for that one statement.
- `user_integrations` (tenant + person): personal installs, one live per person and key.
- `integration_secrets` gains `user_integration_id`; exactly one owner per secret.
- `integration_oauth_states`: hashed single-use states (10-minute expiry) with a sealed PKCE
  verifier; spent once by `UPDATE … WHERE spent_at IS NULL`.
- `integration_events` (insert-only) and `integration_interest` (Notify me).

No existing column changes type; nothing is dropped.

Revision ID: 0890
Revises: 0889
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0890"
down_revision = "0889"
branch_labels = None
depends_on = None

_STATUS = "'connecting', 'connected', 'needs_attention', 'needs_reauth', 'paused', 'disconnected'"
_STATUS_V1 = "'connected', 'needs_attention', 'disconnected'"
_CATEGORIES = "'tax', 'practice', 'erp', 'grc', 'docs', 'comms', 'prod', 'crm', 'hris', 'spend'"
_EVENTS = (
    "'connect_started', 'connected', 'reconnected', 'disconnected', 'synced', 'token_expired', "
    "'health_failed', 'health_recovered', 'run_failed', 'paused', 'resumed'"
)


def _unforced(*statements: str) -> None:
    """Run `statements` as the owner across tenants: FORCE ROW LEVEL SECURITY lifted on the two
    tables for the duration, then restored (one transaction)."""
    for table in ("connections", "firm_integrations"):
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
    for statement in statements:
        op.execute(statement)
    for table in ("connections", "firm_integrations"):
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")


def upgrade() -> None:
    op.execute(
        f"""
        ALTER TABLE integration_catalog
            ADD COLUMN categories text[] NOT NULL DEFAULT '{{}}'
                CONSTRAINT integration_catalog_categories
                CHECK (categories <@ ARRAY[{_CATEGORIES}]::text[]),
            ADD COLUMN description text NULL
                CONSTRAINT integration_catalog_description CHECK (length(description) <= 400),
            ADD COLUMN auth_line text NULL
                CONSTRAINT integration_catalog_auth_line CHECK (length(auth_line) <= 120),
            ADD COLUMN published_at timestamptz NULL,
            ADD COLUMN content_sha256 text NULL
                CONSTRAINT integration_catalog_sha CHECK (content_sha256 ~ '^[0-9a-f]{{64}}$'),
            ADD COLUMN import_id uuid NULL
        """
    )
    op.execute(
        "ALTER TABLE integration_catalog DROP CONSTRAINT integration_catalog_tone_check, "
        "ADD CONSTRAINT integration_catalog_tone_check "
        "CHECK (tone IN ('olive', 'espresso', 'clay', 'ochre', 'brick'))"
    )
    op.execute(
        """
        CREATE TABLE integration_catalog_imports (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            operator text NOT NULL CHECK (operator ~ '^[a-z][a-z0-9._-]{0,60}$'),
            environment text NOT NULL
                CHECK (environment IN ('local', 'test', 'evaluation', 'staging', 'production')),
            dry_run boolean NOT NULL,
            document_sha256 text NOT NULL CHECK (document_sha256 ~ '^[0-9a-f]{64}$'),
            added integer NOT NULL DEFAULT 0 CHECK (added >= 0),
            changed integer NOT NULL DEFAULT 0 CHECK (changed >= 0),
            unpublished integer NOT NULL DEFAULT 0 CHECK (unpublished >= 0),
            note text NOT NULL CHECK (length(btrim(note)) BETWEEN 1 AND 500),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp()
        )
        """
    )
    # Platform content, definers only (as `integration_catalog`, 0194): the operator role writes
    # it, the app reaches it only through a definer, and nobody edits a log row.
    op.execute("REVOKE ALL ON integration_catalog_imports FROM abacus_app")
    op.execute("GRANT SELECT, INSERT ON integration_catalog_imports TO abacus_ops")
    op.execute(
        """
        CREATE FUNCTION integration_catalog_imports_immutable() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'catalogue import log rows are never changed'
                USING ERRCODE = 'insufficient_privilege';
        END
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER integration_catalog_imports_no_update BEFORE UPDATE OR DELETE "
        "ON integration_catalog_imports FOR EACH ROW "
        "EXECUTE FUNCTION integration_catalog_imports_immutable()"
    )

    op.execute(
        f"""
        ALTER TABLE firm_integrations
            DROP CONSTRAINT firm_integrations_status_check,
            ADD CONSTRAINT firm_integrations_status_check CHECK (status IN ({_STATUS})),
            DROP CONSTRAINT firm_integrations_mode_check,
            ADD CONSTRAINT firm_integrations_mode_check
                CHECK (mode IN ('token', 'file_bridge', 'firm_app')),
            ALTER COLUMN created_by DROP NOT NULL,
            ADD CONSTRAINT firm_integrations_creator
                CHECK (created_by IS NOT NULL OR mode = 'firm_app'),
            ADD COLUMN status_reason_code text NULL
                CONSTRAINT firm_integrations_reason
                CHECK (status_reason_code ~ '^[a-z][a-z0-9_]{{1,59}}$'),
            ADD COLUMN status_changed_at timestamptz NULL,
            ADD COLUMN token_renews_at timestamptz NULL,
            ADD COLUMN last_sync_at timestamptz NULL,
            ADD COLUMN granted_scopes text[] NOT NULL DEFAULT '{{}}',
            ADD COLUMN consent_version integer NULL CHECK (consent_version >= 1),
            ADD COLUMN connected_by uuid NULL,
            ADD COLUMN connected_at timestamptz NULL
        """
    )
    op.execute(
        "GRANT INSERT (status_reason_code, status_changed_at, token_renews_at, granted_scopes, "
        "consent_version, connected_by, connected_at) ON firm_integrations TO abacus_app"
    )
    op.execute(
        "GRANT UPDATE (status_reason_code, status_changed_at, token_renews_at, last_sync_at, "
        "granted_scopes, consent_version, connected_by, connected_at) "
        "ON firm_integrations TO abacus_app"
    )
    # The backfill across firms: a connected firm app for every provider with a live client
    # connection, unless the firm already has a live row for it. The migrator owns both tables
    # and has no BYPASSRLS, so FORCE is lifted for this one statement and restored at once (the
    # same transaction; the app role's policies never change).
    _unforced(
        """
        INSERT INTO firm_integrations
            (tenant_id, catalog_key, status, mode, created_by, status_reason_code,
             status_changed_at)
        SELECT DISTINCT c.tenant_id, ic.key, 'connected', 'firm_app', NULL::uuid, 'backfill',
               clock_timestamp()
          FROM connections c
          JOIN integration_catalog ic ON ic.connector_provider = c.provider
         WHERE c.status = 'active'
           AND NOT EXISTS (
               SELECT 1 FROM firm_integrations f
                WHERE f.tenant_id = c.tenant_id AND f.catalog_key = ic.key
                  AND f.status <> 'disconnected'
           )
        """
    )

    op.execute(
        f"""
        CREATE TABLE user_integrations (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            user_id uuid NOT NULL,
            catalog_key text NOT NULL REFERENCES integration_catalog (key),
            status text NOT NULL DEFAULT 'connecting' CHECK (status IN ({_STATUS})),
            status_reason_code text NULL CHECK (status_reason_code ~ '^[a-z][a-z0-9_]{{1,59}}$'),
            status_changed_at timestamptz NULL,
            connected_at timestamptz NULL,
            token_renews_at timestamptz NULL,
            last_sync_at timestamptz NULL,
            granted_scopes text[] NOT NULL DEFAULT '{{}}',
            consent_version integer NULL CHECK (consent_version >= 1),
            version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, user_id) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX user_integrations_one_live ON user_integrations "
        "(tenant_id, user_id, catalog_key) WHERE status <> 'disconnected'"
    )
    op.execute(
        """
        ALTER TABLE integration_secrets
            ALTER COLUMN firm_integration_id DROP NOT NULL,
            ADD COLUMN user_integration_id uuid NULL,
            ADD CONSTRAINT integration_secrets_one_owner
                CHECK (num_nonnulls(firm_integration_id, user_integration_id) = 1),
            ADD CONSTRAINT integration_secrets_user_fk FOREIGN KEY (tenant_id, user_integration_id)
                REFERENCES user_integrations (tenant_id, id)
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX integration_secrets_one_per_user_install ON integration_secrets "
        "(tenant_id, user_integration_id) WHERE user_integration_id IS NOT NULL"
    )
    op.execute("GRANT INSERT (user_integration_id) ON integration_secrets TO abacus_app")
    op.execute(
        """
        CREATE TABLE integration_oauth_states (
            state_sha256 text PRIMARY KEY CHECK (state_sha256 ~ '^[0-9a-f]{64}$'),
            tenant_id uuid NOT NULL,
            user_id uuid NOT NULL,
            catalog_key text NOT NULL REFERENCES integration_catalog (key),
            scope_kind text NOT NULL CHECK (scope_kind IN ('firm', 'user')),
            purpose text NOT NULL CHECK (purpose IN ('connect', 'reconnect')),
            pkce_verifier_sealed bytea NOT NULL CHECK (octet_length(pkce_verifier_sealed) <= 4096),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            expires_at timestamptz NOT NULL,
            spent_at timestamptz NULL,
            CONSTRAINT integration_oauth_states_ten_minutes
                CHECK (expires_at <= created_at + interval '10 minutes'),
            FOREIGN KEY (tenant_id, user_id) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE integration_events (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            install_kind text NOT NULL CHECK (install_kind IN ('firm', 'user')),
            install_id uuid NOT NULL,
            catalog_key text NOT NULL REFERENCES integration_catalog (key),
            kind text NOT NULL CHECK (kind IN ({_EVENTS})),
            at timestamptz NOT NULL,
            actor_user_id uuid NULL,
            subject_type text NULL CHECK (subject_type ~ '^[a-z][a-z0-9_]{{1,59}}$'),
            subject_id uuid NULL,
            run_id uuid NULL,
            code text NULL CHECK (code ~ '^[a-z][a-z0-9_]{{1,59}}$'),
            http_status smallint NULL CHECK (http_status BETWEEN 100 AND 599),
            latency_ms integer NULL CHECK (latency_ms >= 0)
        )
        """
    )
    op.execute(
        "CREATE INDEX integration_events_timeline ON integration_events "
        "(tenant_id, catalog_key, at DESC, id)"
    )
    op.execute(
        """
        CREATE TABLE integration_interest (
            tenant_id uuid NOT NULL,
            user_id uuid NOT NULL,
            catalog_key text NOT NULL REFERENCES integration_catalog (key),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            notified_at timestamptz NULL,
            PRIMARY KEY (tenant_id, user_id, catalog_key),
            FOREIGN KEY (tenant_id, user_id) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    for table, inserts, updates in (
        (
            "user_integrations",
            (
                *("tenant_id", "user_id", "catalog_key", "status", "status_reason_code"),
                *("status_changed_at", "connected_at", "token_renews_at", "granted_scopes"),
                "consent_version",
            ),
            (
                *("status", "status_reason_code", "status_changed_at", "connected_at"),
                *("token_renews_at", "last_sync_at", "granted_scopes", "consent_version"),
                "version",
            ),
        ),
        (
            "integration_oauth_states",
            (
                *("state_sha256", "tenant_id", "user_id", "catalog_key", "scope_kind", "purpose"),
                *("pkce_verifier_sealed", "expires_at"),
            ),
            ("spent_at",),
        ),
        (
            "integration_events",
            (
                *("tenant_id", "install_kind", "install_id", "catalog_key", "kind", "at"),
                *("actor_user_id", "subject_type", "subject_id", "run_id", "code", "http_status"),
                "latency_ms",
            ),
            (),
        ),
        (
            "integration_interest",
            ("tenant_id", "user_id", "catalog_key"),
            ("notified_at",),
        ),
    ):
        tenant_table(op, table)
        op.execute(f"REVOKE UPDATE, DELETE, TRUNCATE ON {table} FROM abacus_app")
        insert_columns(op, table, inserts)
        if updates:
            op.execute(f"GRANT UPDATE ({', '.join(updates)}) ON {table} TO abacus_app")
        else:
            insert_only(op, table)
    # States are purged after 24 hours (the app deletes spent or expired ones).
    op.execute("GRANT DELETE ON integration_oauth_states TO abacus_app")
    op.execute(
        """
        CREATE FUNCTION integration_events_immutable() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'integration events are append-only'
                USING ERRCODE = 'insufficient_privilege';
        END
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER integration_events_no_update BEFORE UPDATE OR DELETE "
        "ON integration_events FOR EACH ROW EXECUTE FUNCTION integration_events_immutable()"
    )


def downgrade() -> None:
    op.execute("DROP TABLE integration_interest")
    op.execute("DROP TABLE integration_events")
    op.execute("DROP FUNCTION integration_events_immutable()")
    op.execute("DROP TABLE integration_oauth_states")
    op.execute("DROP INDEX integration_secrets_one_per_user_install")
    op.execute(
        "ALTER TABLE integration_secrets DROP CONSTRAINT integration_secrets_user_fk, "
        "DROP CONSTRAINT integration_secrets_one_owner, DROP COLUMN user_integration_id"
    )
    op.execute("ALTER TABLE integration_secrets ALTER COLUMN firm_integration_id SET NOT NULL")
    op.execute("DROP TABLE user_integrations")
    # Backfilled and any other v2-only rows go; the v1 CHECKs return.
    _unforced(
        "DELETE FROM firm_integrations WHERE mode = 'firm_app'",
        "UPDATE firm_integrations SET status = 'needs_attention' "
        "WHERE status NOT IN ('connected', 'needs_attention', 'disconnected')",
    )
    op.execute(
        f"""
        ALTER TABLE firm_integrations
            DROP CONSTRAINT firm_integrations_creator,
            DROP COLUMN connected_at, DROP COLUMN connected_by, DROP COLUMN consent_version,
            DROP COLUMN granted_scopes, DROP COLUMN last_sync_at, DROP COLUMN token_renews_at,
            DROP COLUMN status_changed_at, DROP COLUMN status_reason_code,
            ALTER COLUMN created_by SET NOT NULL,
            DROP CONSTRAINT firm_integrations_mode_check,
            ADD CONSTRAINT firm_integrations_mode_check CHECK (mode IN ('token', 'file_bridge')),
            DROP CONSTRAINT firm_integrations_status_check,
            ADD CONSTRAINT firm_integrations_status_check CHECK (status IN ({_STATUS_V1}))
        """
    )
    op.execute("DROP TABLE integration_catalog_imports")
    op.execute("DROP FUNCTION integration_catalog_imports_immutable()")
    op.execute(
        "ALTER TABLE integration_catalog DROP CONSTRAINT integration_catalog_tone_check, "
        "ADD CONSTRAINT integration_catalog_tone_check "
        "CHECK (tone IN ('olive', 'espresso', 'clay', 'ochre'))"
    )
    op.execute(
        "ALTER TABLE integration_catalog DROP COLUMN import_id, DROP COLUMN content_sha256, "
        "DROP COLUMN published_at, DROP COLUMN auth_line, DROP COLUMN description, "
        "DROP COLUMN categories"
    )
