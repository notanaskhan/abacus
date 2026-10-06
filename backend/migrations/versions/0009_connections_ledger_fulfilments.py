"""Connections, sync runs, ledger snapshots, trial balance lines, fulfilments (TASK-010 design §4).

- Ledger snapshots and their lines are immutable like evidence (ADR-004): insert-only for the app,
  and a trigger rejects UPDATE, DELETE and TRUNCATE for every role.
- Fulfilments are insert-only (confirmation states arrive with review, later).
- Sync runs change status as a pull proceeds; the app may update only the result columns, a
  trigger keeps them forward-only and write-once, and composite keys tie the connection,
  engagement, snapshot and evidence to one client entity. They record every pull (ADR-040).
- Connections are created by tooling for SPEC-000; the app may only read them and change status.
- Evidence versions now reference their ledger snapshot.

Revision ID: 0009
Revises: 0008
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

_TABLES = ("connections", "sync_runs", "ledger_snapshots", "trial_balance_lines", "fulfilments")


def upgrade() -> None:
    # Lets other tables require that a request item belongs to a given engagement.
    op.execute(
        "ALTER TABLE request_items ADD CONSTRAINT request_items_engagement_item "
        "UNIQUE (tenant_id, engagement_id, id)"
    )
    # Let runs and fulfilments prove their rows belong together (same entity, same engagement).
    op.execute(
        "ALTER TABLE engagements ADD CONSTRAINT engagements_entity_engagement "
        "UNIQUE (tenant_id, client_entity_id, id)"
    )
    op.execute(
        "ALTER TABLE evidence_versions ADD CONSTRAINT evidence_versions_engagement_version "
        "UNIQUE (tenant_id, engagement_id, id)"
    )
    op.execute(
        """
        CREATE TABLE connections (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            client_entity_id uuid NOT NULL,
            provider text NOT NULL CHECK (provider IN ('fake')),
            status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'revoked')),
            scopes text[] NOT NULL DEFAULT '{}',
            expires_at timestamptz NULL,
            created_by text NOT NULL CHECK (length(created_by) BETWEEN 1 AND 200),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, client_entity_id, id),
            FOREIGN KEY (tenant_id, client_entity_id) REFERENCES client_entities (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE sync_runs (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            client_entity_id uuid NOT NULL,
            connection_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            request_item_id uuid NOT NULL,
            dataset text NOT NULL CHECK (dataset IN ('trial_balance')),
            period_start date NOT NULL,
            period_end date NOT NULL,
            status text NOT NULL DEFAULT 'running'
                CHECK (status IN ('running', 'succeeded', 'failed_validation', 'failed')),
            raw_storage_key text NULL,
            raw_version_id text NULL,
            raw_fingerprint text NULL CHECK (raw_fingerprint ~ '^[0-9a-f]{64}$'),
            raw_size_bytes bigint NULL CHECK (raw_size_bytes >= 0),
            raw_pulled_at timestamptz NULL,
            source text NULL CHECK (source ~ '^[a-z][a-z0-9_]{0,49}$'),
            snapshot_id uuid NULL,
            evidence_version_id uuid NULL,
            failure_code text NULL CHECK (failure_code ~ '^[a-z][a-z_]{0,49}$'),
            started_by text NOT NULL CHECK (length(started_by) BETWEEN 1 AND 200),
            started_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            finished_at timestamptz NULL,
            UNIQUE (tenant_id, id),
            CONSTRAINT sync_runs_period CHECK (period_end >= period_start),
            CONSTRAINT sync_runs_finished CHECK ((status = 'running') = (finished_at IS NULL)),
            CONSTRAINT sync_runs_failure_code
                CHECK ((status IN ('failed', 'failed_validation')) = (failure_code IS NOT NULL)),
            CONSTRAINT sync_runs_succeeded_complete CHECK (
                status <> 'succeeded'
                OR (raw_fingerprint IS NOT NULL AND snapshot_id IS NOT NULL
                    AND evidence_version_id IS NOT NULL)
            ),
            CONSTRAINT sync_runs_failed_validation_unsnapshotted
                CHECK (status <> 'failed_validation' OR snapshot_id IS NULL),
            -- The connection, the engagement and the snapshot all belong to the run's entity.
            FOREIGN KEY (tenant_id, client_entity_id, connection_id)
                REFERENCES connections (tenant_id, client_entity_id, id),
            FOREIGN KEY (tenant_id, client_entity_id, engagement_id)
                REFERENCES engagements (tenant_id, client_entity_id, id),
            FOREIGN KEY (tenant_id, engagement_id, request_item_id)
                REFERENCES request_items (tenant_id, engagement_id, id),
            FOREIGN KEY (tenant_id, engagement_id, evidence_version_id)
                REFERENCES evidence_versions (tenant_id, engagement_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE ledger_snapshots (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            client_entity_id uuid NOT NULL,
            period_start date NOT NULL,
            period_end date NOT NULL,
            pulled_at timestamptz NOT NULL,
            source text NOT NULL CHECK (length(source) BETWEEN 1 AND 100),
            raw_fingerprint text NOT NULL CHECK (raw_fingerprint ~ '^[0-9a-f]{64}$'),
            line_count integer NOT NULL CHECK (line_count >= 0),
            total_debit numeric(20, 2) NOT NULL CHECK (total_debit >= 0),
            total_credit numeric(20, 2) NOT NULL CHECK (total_credit >= 0),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, client_entity_id, id),
            -- The same pull of the same period gives the same snapshot (§12 idempotency).
            CONSTRAINT ledger_snapshots_pull
                UNIQUE (tenant_id, client_entity_id, period_start, period_end, raw_fingerprint),
            -- A snapshot exists only for a validated trial balance (ADR-038).
            CONSTRAINT ledger_snapshots_balanced CHECK (total_debit = total_credit),
            CONSTRAINT ledger_snapshots_period CHECK (period_end >= period_start),
            FOREIGN KEY (tenant_id, client_entity_id) REFERENCES client_entities (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE trial_balance_lines (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            snapshot_id uuid NOT NULL,
            account_code text NOT NULL CHECK (length(account_code) BETWEEN 1 AND 50),
            account_name text NOT NULL CHECK (length(account_name) BETWEEN 1 AND 200),
            debit numeric(20, 2) NOT NULL CHECK (debit >= 0),
            credit numeric(20, 2) NOT NULL CHECK (credit >= 0),
            source_ref text NOT NULL CHECK (length(source_ref) BETWEEN 1 AND 200),
            UNIQUE (tenant_id, id),
            CONSTRAINT trial_balance_lines_account UNIQUE (tenant_id, snapshot_id, account_code),
            FOREIGN KEY (tenant_id, snapshot_id) REFERENCES ledger_snapshots (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE fulfilments (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            request_item_id uuid NOT NULL,
            evidence_version_id uuid NOT NULL,
            created_by_kind text NOT NULL CHECK (created_by_kind IN ('rule', 'human', 'agent')),
            created_by_id text NOT NULL CHECK (length(created_by_id) BETWEEN 1 AND 200),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            CONSTRAINT fulfilments_once UNIQUE (tenant_id, request_item_id, evidence_version_id),
            -- The evidence fulfils an item of its own engagement.
            FOREIGN KEY (tenant_id, engagement_id, request_item_id)
                REFERENCES request_items (tenant_id, engagement_id, id),
            FOREIGN KEY (tenant_id, engagement_id, evidence_version_id)
                REFERENCES evidence_versions (tenant_id, engagement_id, id)
        )
        """
    )
    op.execute(
        "ALTER TABLE sync_runs ADD CONSTRAINT sync_runs_snapshot_fkey "
        "FOREIGN KEY (tenant_id, client_entity_id, snapshot_id) "
        "REFERENCES ledger_snapshots (tenant_id, client_entity_id, id)"
    )
    op.execute(
        "ALTER TABLE evidence_versions ADD CONSTRAINT evidence_versions_snapshot_fkey "
        "FOREIGN KEY (tenant_id, snapshot_id) REFERENCES ledger_snapshots (tenant_id, id)"
    )
    op.execute("CREATE INDEX sync_runs_request_item ON sync_runs (tenant_id, request_item_id)")
    op.execute("CREATE INDEX sync_runs_status ON sync_runs (tenant_id, status, started_at)")
    # One live (or successful) run per item and period: a second trigger gets the same run.
    op.execute(
        "CREATE UNIQUE INDEX sync_runs_one_active ON sync_runs "
        "(tenant_id, request_item_id, period_start, period_end) "
        "WHERE status IN ('running', 'succeeded')"
    )
    op.execute("CREATE INDEX fulfilments_request_item ON fulfilments (tenant_id, request_item_id)")
    for table in _TABLES:
        tenant_table(op, table)

    # Connections: tooling creates them in SPEC-000; the app reads them and may revoke.
    op.execute("REVOKE INSERT, UPDATE, DELETE ON connections FROM abacus_app")
    op.execute("GRANT UPDATE (status) ON connections TO abacus_app")
    # Sync runs: created by the app, then only their result changes.
    op.execute("REVOKE UPDATE, DELETE ON sync_runs FROM abacus_app")
    insert_columns(
        op,
        "sync_runs",
        (
            "id",
            "tenant_id",
            "client_entity_id",
            "connection_id",
            "engagement_id",
            "request_item_id",
            "dataset",
            "period_start",
            "period_end",
            "started_by",
        ),
    )
    op.execute(
        "GRANT UPDATE (status, raw_storage_key, raw_version_id, raw_fingerprint, raw_size_bytes, "
        "raw_pulled_at, source, snapshot_id, evidence_version_id, failure_code, finished_at) "
        "ON sync_runs TO abacus_app"
    )
    # Ledger and fulfilments: insert-only.
    for table in ("ledger_snapshots", "trial_balance_lines", "fulfilments"):
        insert_only(op, table)
    insert_columns(
        op,
        "ledger_snapshots",
        (
            "id",
            "tenant_id",
            "client_entity_id",
            "period_start",
            "period_end",
            "pulled_at",
            "source",
            "raw_fingerprint",
            "line_count",
            "total_debit",
            "total_credit",
        ),
    )
    insert_columns(
        op,
        "trial_balance_lines",
        (
            "id",
            "tenant_id",
            "snapshot_id",
            "account_code",
            "account_name",
            "debit",
            "credit",
            "source_ref",
        ),
    )
    insert_columns(
        op,
        "fulfilments",
        (
            "id",
            "tenant_id",
            "engagement_id",
            "request_item_id",
            "evidence_version_id",
            "created_by_kind",
            "created_by_id",
        ),
    )

    # Second layer for ledger data (ADR-004): no role changes or removes it.
    op.execute(
        """
        CREATE FUNCTION ledger_immutable() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'ledger snapshots are immutable (ADR-004)'
                USING ERRCODE = 'insufficient_privilege';
        END
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER ledger_snapshots_no_update_or_delete "
        "BEFORE UPDATE OR DELETE ON ledger_snapshots "
        "FOR EACH ROW EXECUTE FUNCTION ledger_immutable()"
    )
    op.execute(
        "CREATE TRIGGER ledger_snapshots_no_truncate BEFORE TRUNCATE ON ledger_snapshots "
        "FOR EACH STATEMENT EXECUTE FUNCTION ledger_immutable()"
    )
    op.execute(
        "CREATE TRIGGER trial_balance_lines_no_update_or_delete "
        "BEFORE UPDATE OR DELETE ON trial_balance_lines "
        "FOR EACH ROW EXECUTE FUNCTION ledger_immutable()"
    )
    op.execute(
        "CREATE TRIGGER trial_balance_lines_no_truncate BEFORE TRUNCATE ON trial_balance_lines "
        "FOR EACH STATEMENT EXECUTE FUNCTION ledger_immutable()"
    )

    # Sync runs are the pull log (ADR-040): a run only moves forward, and what it recorded stays.
    op.execute(
        """
        CREATE FUNCTION sync_runs_forward_only() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF OLD.status <> 'running' THEN
                RAISE EXCEPTION 'sync run % is finished', OLD.id
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            -- Write-once: a recorded result may be set once, never changed or cleared.
            IF (OLD.raw_storage_key IS NOT NULL
                AND NEW.raw_storage_key IS DISTINCT FROM OLD.raw_storage_key)
               OR (OLD.raw_version_id IS NOT NULL
                AND NEW.raw_version_id IS DISTINCT FROM OLD.raw_version_id)
               OR (OLD.raw_fingerprint IS NOT NULL
                AND NEW.raw_fingerprint IS DISTINCT FROM OLD.raw_fingerprint)
               OR (OLD.raw_size_bytes IS NOT NULL
                AND NEW.raw_size_bytes IS DISTINCT FROM OLD.raw_size_bytes)
               OR (OLD.raw_pulled_at IS NOT NULL
                AND NEW.raw_pulled_at IS DISTINCT FROM OLD.raw_pulled_at)
               OR (OLD.source IS NOT NULL AND NEW.source IS DISTINCT FROM OLD.source)
               OR (OLD.snapshot_id IS NOT NULL
                AND NEW.snapshot_id IS DISTINCT FROM OLD.snapshot_id)
               OR (OLD.evidence_version_id IS NOT NULL
                AND NEW.evidence_version_id IS DISTINCT FROM OLD.evidence_version_id) THEN
                RAISE EXCEPTION 'sync run % results are write-once', OLD.id
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER sync_runs_forward_only BEFORE UPDATE ON sync_runs "
        "FOR EACH ROW EXECUTE FUNCTION sync_runs_forward_only()"
    )
    op.execute(
        """
        CREATE FUNCTION connections_no_reactivation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF OLD.status = 'revoked' AND NEW.status <> 'revoked' THEN
                RAISE EXCEPTION 'a revoked connection stays revoked'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER connections_no_reactivation BEFORE UPDATE ON connections "
        "FOR EACH ROW EXECUTE FUNCTION connections_no_reactivation()"
    )
    # Lines join a snapshot only in the transaction that created it: a finished snapshot can't
    # gain lines that its header totals don't account for (ADR-004).
    op.execute(
        """
        CREATE FUNCTION trial_balance_lines_with_snapshot() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM ledger_snapshots s
                WHERE s.tenant_id = NEW.tenant_id AND s.id = NEW.snapshot_id
                  AND s.xmin::text::bigint = (txid_current() % 4294967296)
            ) THEN
                RAISE EXCEPTION 'lines can only be added with their snapshot'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER trial_balance_lines_with_snapshot BEFORE INSERT ON trial_balance_lines "
        "FOR EACH ROW EXECUTE FUNCTION trial_balance_lines_with_snapshot()"
    )


def downgrade() -> None:
    op.execute(
        "DO $$ BEGIN "
        "IF EXISTS (SELECT 1 FROM ledger_snapshots) OR EXISTS (SELECT 1 FROM sync_runs) "
        "OR EXISTS (SELECT 1 FROM fulfilments) OR EXISTS (SELECT 1 FROM connections) THEN "
        "RAISE EXCEPTION 'refusing to downgrade: connections, runs, ledger data or fulfilments "
        "exist (ADR-004, ADR-040)'; "
        "END IF; END $$"
    )
    op.execute("ALTER TABLE evidence_versions DROP CONSTRAINT evidence_versions_snapshot_fkey")
    op.execute("DROP TABLE fulfilments")
    op.execute("ALTER TABLE sync_runs DROP CONSTRAINT sync_runs_snapshot_fkey")
    op.execute("DROP TABLE trial_balance_lines")
    op.execute("DROP FUNCTION trial_balance_lines_with_snapshot()")
    op.execute("DROP TABLE ledger_snapshots")
    op.execute("DROP FUNCTION ledger_immutable()")
    op.execute("DROP TABLE sync_runs")
    op.execute("DROP FUNCTION sync_runs_forward_only()")
    op.execute("DROP TABLE connections")
    op.execute("DROP FUNCTION connections_no_reactivation()")
    op.execute(
        "ALTER TABLE evidence_versions DROP CONSTRAINT evidence_versions_engagement_version"
    )
    op.execute("ALTER TABLE engagements DROP CONSTRAINT engagements_entity_engagement")
    op.execute("ALTER TABLE request_items DROP CONSTRAINT request_items_engagement_item")
