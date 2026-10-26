"""Entity-scoped connections (A-02-T13; TASK-1340; SPEC-333 AC-35 to AC-48; A-02 §4.2; ADR-040,
ADR-045, P-38; DEC-439). Written expand-only; the downgrade is for a local database.

- `connections`: the provider CHECK becomes the key grammar (`^[a-z][a-z0-9_]{1,49}$`; which
  providers exist is the adapter registry's job, A-02-T12, and `fake` and `import` still fit),
  for `connection_states` too. New columns: `category` (backfilled `ledger`, the only kind that
  exists), `external_account_ref` (the provider's company or account id), `display_label` (the
  masked label, "Front Range Bank ••4410"; client content, rendered as text), who connected and
  when, `reauth_due_at`, `last_sync_at` and `status_reason_code` (C20's reasons). Status codes
  are unchanged (`active`, `needs_attention`, `revoked`).
  Uniqueness: one live connection per entity (`connections_one_live`) becomes one live
  connection per entity, provider and account (`connections_one_live_account`) and one live
  ledger per entity (`connections_one_live_ledger`, ADR-045; A-09 relaxes it for OneWorld), so a
  bank feed may sit beside the ledger and a second QuickBooks company may not.
- `sync_runs`: `request_item_id` becomes nullable; `trigger` (`request_item`, backfilled, or
  `on_demand`, `schedule`, `export`) says why a run exists, and only a request-item run names a
  request item (CHECK); `label` (the TB label a pull lands as); `dataset` widens to
  `prior_trial_balance`. Results stay write-once (`sync_runs_forward_only`, unchanged).
- `connection_consents` (insert-only, ADR-004): what the client agreed to before the provider's
  sheet: the catalogue key and consent version, the will and won't lists and the authorization
  text as shown, the person and a SHA-256 of their IP. Never updated: the connection a consent
  produced is recorded in `connection_consent_links` (insert-only, one per consent, on the
  consent's own client entity: both its keys carry `client_entity_id`).
- `reconnect_requests`: the firm asking the client to reconnect; one open request per connection
  (`fulfilled_at IS NULL`); the app may set `fulfilled_at` only.

The secret crypto-erase path is untouched: `connection_secrets` is still deleted on revoke
(DEC-379's `connection.disconnect` runs it in A-02-T16).

`down_revision` is 0194 on this branch (S10 wave B); the merge re-points the chain.

Revision ID: 0195
Revises: 0194
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0195"
down_revision = "0194"
branch_labels = None
depends_on = None

_KEY = "'^[a-z][a-z0-9_]{1,49}$'"
_CATEGORIES = "('ledger', 'bank_feed', 'card_feed', 'sales', 'payroll', 'hr', 'ticketing', 'grc')"
_REASONS = "('token_expired', 'invalid_grant', 'sync_failed', 'provider_unavailable')"
_LABELS = "('standard', 'interim', 'prior', 'budget', 'preliminary')"
_NEW_INSERT = (
    "category",
    "external_account_ref",
    "display_label",
    "connected_by_user_id",
    "connected_at",
)
_NEW_UPDATE = (
    "connected_by_user_id",
    "connected_at",
    "reauth_due_at",
    "last_sync_at",
    "status_reason_code",
)


def upgrade() -> None:
    for table in ("connections", "connection_states"):
        op.execute(
            f"ALTER TABLE {table} DROP CONSTRAINT {table}_provider_check, "
            f"ADD CONSTRAINT {table}_provider_check CHECK (provider ~ {_KEY})"
        )
    op.execute(
        f"""
        ALTER TABLE connections
            ADD COLUMN category text NOT NULL DEFAULT 'ledger'
                CONSTRAINT connections_category_check CHECK (category IN {_CATEGORIES}),
            ADD COLUMN external_account_ref text NULL
                CONSTRAINT connections_external_account_ref_check
                CHECK (length(external_account_ref) BETWEEN 1 AND 100),
            ADD COLUMN display_label text NULL
                CONSTRAINT connections_display_label_check
                CHECK (length(display_label) BETWEEN 1 AND 120),
            ADD COLUMN connected_by_user_id uuid NULL,
            ADD COLUMN connected_at timestamptz NULL,
            ADD COLUMN reauth_due_at timestamptz NULL,
            ADD COLUMN last_sync_at timestamptz NULL,
            ADD COLUMN status_reason_code text NULL
                CONSTRAINT connections_status_reason_code_check
                CHECK (status_reason_code IN {_REASONS}),
            ADD CONSTRAINT connections_connected_whole
                CHECK ((connected_by_user_id IS NULL) = (connected_at IS NULL))
        """
    )
    op.execute("DROP INDEX connections_one_live")
    op.execute(
        "CREATE UNIQUE INDEX connections_one_live_account ON connections "
        "(tenant_id, client_entity_id, provider, coalesce(external_account_ref, '')) "
        "WHERE status <> 'revoked'"
    )
    op.execute(
        "CREATE UNIQUE INDEX connections_one_live_ledger ON connections "
        "(tenant_id, client_entity_id) WHERE status <> 'revoked' AND category = 'ledger'"
    )
    op.execute(f"GRANT INSERT ({', '.join(_NEW_INSERT)}) ON connections TO abacus_app")
    op.execute(f"GRANT UPDATE ({', '.join(_NEW_UPDATE)}) ON connections TO abacus_app")

    op.execute(
        f"""
        ALTER TABLE sync_runs
            ALTER COLUMN request_item_id DROP NOT NULL,
            ADD COLUMN trigger text NOT NULL DEFAULT 'request_item'
                CONSTRAINT sync_runs_trigger_check
                CHECK (trigger IN ('request_item', 'on_demand', 'schedule', 'export')),
            ADD COLUMN label text NULL
                CONSTRAINT sync_runs_label_check CHECK (label IN {_LABELS}),
            DROP CONSTRAINT sync_runs_dataset_check,
            ADD CONSTRAINT sync_runs_dataset_check
                CHECK (dataset IN ('trial_balance', 'prior_trial_balance')),
            ADD CONSTRAINT sync_runs_trigger_item
                CHECK ((trigger = 'request_item') = (request_item_id IS NOT NULL))
        """
    )
    op.execute("GRANT INSERT (trigger, label) ON sync_runs TO abacus_app")

    op.execute(
        """
        CREATE TABLE connection_consents (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            connection_id uuid NULL,
            client_entity_id uuid NOT NULL,
            catalog_key text NOT NULL CHECK (catalog_key ~ '^[a-z][a-z0-9_]{1,49}$'),
            consent_version integer NOT NULL CHECK (consent_version >= 1),
            will text[] NOT NULL CHECK (cardinality(will) BETWEEN 1 AND 10),
            wont text[] NOT NULL CHECK (cardinality(wont) BETWEEN 1 AND 10),
            authorization_text text NOT NULL
                CHECK (length(authorization_text) BETWEEN 1 AND 400),
            authorised_by_user_id uuid NOT NULL,
            ip_sha256 text NOT NULL CHECK (ip_sha256 ~ '^[0-9a-f]{64}$'),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, client_entity_id, id),
            FOREIGN KEY (tenant_id, client_entity_id) REFERENCES client_entities (tenant_id, id),
            FOREIGN KEY (tenant_id, client_entity_id, connection_id)
                REFERENCES connections (tenant_id, client_entity_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE connection_consent_links (
            consent_id uuid PRIMARY KEY,
            tenant_id uuid NOT NULL,
            client_entity_id uuid NOT NULL,
            connection_id uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            -- The consent and the connection belong to the same client entity (review M2).
            FOREIGN KEY (tenant_id, client_entity_id, consent_id)
                REFERENCES connection_consents (tenant_id, client_entity_id, id),
            FOREIGN KEY (tenant_id, client_entity_id, connection_id)
                REFERENCES connections (tenant_id, client_entity_id, id)
        )
        """
    )
    for table in ("connection_consents", "connection_consent_links"):
        tenant_table(op, table)
        insert_only(op, table)
    insert_columns(
        op,
        "connection_consents",
        (
            "tenant_id",
            "connection_id",
            "client_entity_id",
            "catalog_key",
            "consent_version",
            "will",
            "wont",
            "authorization_text",
            "authorised_by_user_id",
            "ip_sha256",
        ),
    )
    insert_columns(
        op,
        "connection_consent_links",
        ("consent_id", "tenant_id", "client_entity_id", "connection_id"),
    )
    op.execute(
        """
        CREATE FUNCTION connection_consents_immutable() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'connection consents are immutable (ADR-004)'
                USING ERRCODE = 'insufficient_privilege';
        END
        $$
        """
    )
    for table in ("connection_consents", "connection_consent_links"):
        op.execute(
            f"CREATE TRIGGER {table}_no_update_or_delete BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION connection_consents_immutable()"
        )
        op.execute(
            f"CREATE TRIGGER {table}_no_truncate BEFORE TRUNCATE ON {table} "
            "FOR EACH STATEMENT EXECUTE FUNCTION connection_consents_immutable()"
        )

    op.execute(
        """
        CREATE TABLE reconnect_requests (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            connection_id uuid NOT NULL,
            requested_by_user_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT abacus_now(),
            fulfilled_at timestamptz NULL CHECK (fulfilled_at >= created_at),
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, connection_id) REFERENCES connections (tenant_id, id),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id),
            FOREIGN KEY (tenant_id, requested_by_user_id)
                REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX reconnect_requests_one_open ON reconnect_requests "
        "(tenant_id, connection_id) WHERE fulfilled_at IS NULL"
    )
    tenant_table(op, "reconnect_requests")
    op.execute("REVOKE UPDATE, DELETE ON reconnect_requests FROM abacus_app")
    insert_columns(
        op,
        "reconnect_requests",
        ("tenant_id", "connection_id", "requested_by_user_id", "engagement_id"),
    )
    op.execute("GRANT UPDATE (fulfilled_at) ON reconnect_requests TO abacus_app")


def downgrade() -> None:
    op.execute("DROP TABLE reconnect_requests")
    op.execute("DROP TABLE connection_consent_links")
    op.execute("DROP TABLE connection_consents")
    op.execute("DROP FUNCTION connection_consents_immutable()")
    op.execute("REVOKE INSERT (trigger, label) ON sync_runs FROM abacus_app")
    op.execute(
        """
        ALTER TABLE sync_runs
            DROP CONSTRAINT sync_runs_trigger_item,
            DROP CONSTRAINT sync_runs_dataset_check,
            ADD CONSTRAINT sync_runs_dataset_check CHECK (dataset IN ('trial_balance')),
            DROP COLUMN label,
            DROP COLUMN trigger,
            ALTER COLUMN request_item_id SET NOT NULL
        """
    )
    op.execute(f"REVOKE UPDATE ({', '.join(_NEW_UPDATE)}) ON connections FROM abacus_app")
    op.execute(f"REVOKE INSERT ({', '.join(_NEW_INSERT)}) ON connections FROM abacus_app")
    op.execute("DROP INDEX connections_one_live_ledger")
    op.execute("DROP INDEX connections_one_live_account")
    op.execute(
        "CREATE UNIQUE INDEX connections_one_live ON connections (tenant_id, client_entity_id) "
        "WHERE status <> 'revoked'"
    )
    op.execute(
        """
        ALTER TABLE connections
            DROP CONSTRAINT connections_connected_whole,
            DROP COLUMN status_reason_code,
            DROP COLUMN last_sync_at,
            DROP COLUMN reauth_due_at,
            DROP COLUMN connected_at,
            DROP COLUMN connected_by_user_id,
            DROP COLUMN display_label,
            DROP COLUMN external_account_ref,
            DROP COLUMN category
        """
    )
    for table in ("connections", "connection_states"):
        op.execute(
            f"ALTER TABLE {table} DROP CONSTRAINT {table}_provider_check, "
            f"ADD CONSTRAINT {table}_provider_check CHECK (provider IN ('fake', 'import'))"
        )
