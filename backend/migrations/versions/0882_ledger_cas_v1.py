"""C-01-T10 (S44; TASK-8010; C-01 §4.2 T10; SPEC-655 F5, F6): `ledger_cas_v1`, expand-only, red.

The CAS ledger read for closes (C9 v2.1, C-01-T07):
- `ledger_accounts` (ledger): the QuickBooks chart of accounts as of a snapshot (classification,
  type, subtype, mask, contra, active), insert-only per snapshot and immutable for every role
  (`ledger_immutable()`, ADR-004).
- `ledger_snapshots` gains `period_kind` ('year' or 'month', default 'year') and `period`
  (`YYYY-MM`, required for a month). New columns with defaults: no existing row is updated.
- `gl_entries` gains the register fields a close reads: `offset_account_ref`, `payee`,
  `txn_type`, `external_txn_id` (nullable). Cleared status is not stored: the reconciliation
  computes outstanding items from its own matches (C-01 §7, R2).
- `sync_schedules` (connections): one row per connection, cadence, business hours, pause reason,
  next tick and the change-data-capture cursor; the sync workflow (C-01-T17) moves them.
- `sync_runs` gains `api_calls` and a wider `dataset` (accounts, gl_detail, trial_balance_month).
- `connection_meter_usage` (connections): metered provider calls per firm, provider and month,
  against the firm's budget (QC-5).

Read only: nothing here writes to a client system (CONN-001, ADR-040).

Revision ID: 0882
Revises: 0881
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0882"
down_revision = "0881"
branch_labels = None
depends_on = None

_PERIOD = "~ '^[0-9]{4}-(0[1-9]|1[0-2])$'"
_DATASETS_OLD = "('trial_balance', 'prior_trial_balance')"
_DATASETS_NEW = (
    "('trial_balance', 'prior_trial_balance', 'accounts', 'gl_detail', 'trial_balance_month')"
)


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE ledger_accounts (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            client_entity_id uuid NOT NULL,
            snapshot_id uuid NOT NULL,
            external_id text NOT NULL CHECK (length(external_id) BETWEEN 1 AND 64),
            number text NULL CHECK (length(number) <= 50),
            name text NOT NULL CHECK (length(name) BETWEEN 1 AND 200),
            classification text NOT NULL
                CHECK (classification IN ('asset', 'liability', 'equity', 'income', 'expense')),
            account_type text NOT NULL CHECK (length(account_type) BETWEEN 1 AND 80),
            account_subtype text NULL CHECK (length(account_subtype) <= 80),
            parent_external_id text NULL CHECK (length(parent_external_id) <= 64),
            mask text NULL CHECK (mask ~ '^••[0-9]{4}$'),
            is_contra boolean NOT NULL DEFAULT false,
            active boolean NOT NULL DEFAULT true,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (snapshot_id, external_id),
            FOREIGN KEY (tenant_id, client_entity_id, snapshot_id)
                REFERENCES ledger_snapshots (tenant_id, client_entity_id, id)
        )
        """
    )
    tenant_table(op, "ledger_accounts")
    op.execute("REVOKE UPDATE, DELETE, TRUNCATE ON ledger_accounts FROM abacus_app")
    insert_columns(
        op,
        "ledger_accounts",
        ("tenant_id", "client_entity_id", "snapshot_id", "external_id", "number", "name",
         "classification", "account_type", "account_subtype", "parent_external_id", "mask",
         "is_contra", "active"),
    )  # fmt: skip
    insert_only(op, "ledger_accounts")
    op.execute(
        "CREATE TRIGGER ledger_accounts_no_update_or_delete "
        "BEFORE UPDATE OR DELETE ON ledger_accounts "
        "FOR EACH ROW EXECUTE FUNCTION ledger_immutable()"
    )
    op.execute(
        "CREATE TRIGGER ledger_accounts_no_truncate BEFORE TRUNCATE ON ledger_accounts "
        "FOR EACH STATEMENT EXECUTE FUNCTION ledger_immutable()"
    )

    op.execute(
        f"""
        ALTER TABLE ledger_snapshots
            ADD COLUMN period_kind text NOT NULL DEFAULT 'year'
                CONSTRAINT ledger_snapshots_period_kind CHECK (period_kind IN ('year', 'month')),
            ADD COLUMN period text NULL
                CONSTRAINT ledger_snapshots_month CHECK (period {_PERIOD}),
            ADD CONSTRAINT ledger_snapshots_month_period
                CHECK (period_kind = 'year' OR period IS NOT NULL)
        """
    )
    op.execute("GRANT INSERT (period_kind, period) ON ledger_snapshots TO abacus_app")

    op.execute(
        """
        ALTER TABLE gl_entries
            ADD COLUMN offset_account_ref text NULL
                CONSTRAINT gl_entries_offset_account_ref CHECK (length(offset_account_ref) <= 64),
            ADD COLUMN payee text NULL CONSTRAINT gl_entries_payee CHECK (length(payee) <= 200),
            ADD COLUMN txn_type text NULL
                CONSTRAINT gl_entries_txn_type CHECK (length(txn_type) <= 60),
            ADD COLUMN external_txn_id text NULL
                CONSTRAINT gl_entries_external_txn_id CHECK (length(external_txn_id) <= 64)
        """
    )
    op.execute(
        "GRANT INSERT (offset_account_ref, payee, txn_type, external_txn_id) "
        "ON gl_entries TO abacus_app"
    )

    op.execute(
        """
        CREATE TABLE sync_schedules (
            connection_id uuid PRIMARY KEY,
            tenant_id uuid NOT NULL,
            cadence text NOT NULL DEFAULT 'hourly'
                CHECK (cadence IN ('hourly', 'daily', 'on_demand')),
            business_hours jsonb NOT NULL DEFAULT '{"start": "07:00", "end": "19:00"}'::jsonb
                CHECK (jsonb_typeof(business_hours) = 'object'),
            paused_reason text NULL CHECK (paused_reason ~ '^[a-z][a-z0-9_]{0,63}$'),
            next_run_at timestamptz NULL,
            cdc_cursor timestamptz NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            FOREIGN KEY (tenant_id, connection_id) REFERENCES connections (tenant_id, id)
        )
        """
    )
    tenant_table(op, "sync_schedules")
    op.execute("REVOKE UPDATE, DELETE, TRUNCATE ON sync_schedules FROM abacus_app")
    insert_columns(
        op,
        "sync_schedules",
        ("tenant_id", "connection_id", "cadence", "business_hours", "next_run_at"),
    )
    op.execute(
        "GRANT UPDATE (cadence, business_hours, paused_reason, next_run_at, cdc_cursor) "
        "ON sync_schedules TO abacus_app"
    )

    op.execute(
        f"""
        ALTER TABLE sync_runs
            ADD COLUMN api_calls integer NOT NULL DEFAULT 0
                CONSTRAINT sync_runs_api_calls CHECK (api_calls >= 0),
            DROP CONSTRAINT sync_runs_dataset_check,
            ADD CONSTRAINT sync_runs_dataset_check CHECK (dataset IN {_DATASETS_NEW})
        """
    )
    op.execute("GRANT UPDATE (api_calls) ON sync_runs TO abacus_app")

    op.execute(
        f"""
        CREATE TABLE connection_meter_usage (
            tenant_id uuid NOT NULL,
            provider text NOT NULL CHECK (provider ~ '^[a-z][a-z0-9_]{{0,49}}$'),
            month text NOT NULL CHECK (month {_PERIOD}),
            calls integer NOT NULL DEFAULT 0 CHECK (calls >= 0),
            budget integer NULL CHECK (budget >= 0),
            updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            PRIMARY KEY (tenant_id, provider, month)
        )
        """
    )
    tenant_table(op, "connection_meter_usage")
    op.execute("REVOKE UPDATE, DELETE, TRUNCATE ON connection_meter_usage FROM abacus_app")
    insert_columns(op, "connection_meter_usage", ("tenant_id", "provider", "month", "budget"))
    op.execute("GRANT UPDATE (calls, budget, updated_at) ON connection_meter_usage TO abacus_app")


def downgrade() -> None:
    op.execute("DROP TABLE connection_meter_usage")
    op.execute("REVOKE UPDATE (api_calls) ON sync_runs FROM abacus_app")
    op.execute(
        f"""
        ALTER TABLE sync_runs
            DROP CONSTRAINT sync_runs_dataset_check,
            ADD CONSTRAINT sync_runs_dataset_check CHECK (dataset IN {_DATASETS_OLD}),
            DROP COLUMN api_calls
        """
    )
    op.execute("DROP TABLE sync_schedules")
    op.execute(
        "ALTER TABLE gl_entries DROP COLUMN external_txn_id, DROP COLUMN txn_type, "
        "DROP COLUMN payee, DROP COLUMN offset_account_ref"
    )
    op.execute(
        "ALTER TABLE ledger_snapshots DROP CONSTRAINT ledger_snapshots_month_period, "
        "DROP COLUMN period, DROP COLUMN period_kind"
    )
    op.execute("DROP TABLE ledger_accounts")
