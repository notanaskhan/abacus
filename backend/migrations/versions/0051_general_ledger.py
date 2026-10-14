"""General ledger detail (SPEC-034; TASK-069; ADR-004, ADR-038).

ledger: `gl_snapshots` (one per entity, period and raw file, reconciled to a trial balance
snapshot), `gl_account_balances` (each account's opening, debits, credits and closing, with
whether its opening was derived) and `gl_entries` (the postings). All three are insert-only and,
like trial balance snapshots, immutable for every role; balances and entries join a snapshot only
in the transaction that created it. connections: `gl_imports`, an upload and where it stands;
the app updates only its status columns.

Revision ID: 0051
Revises: 0050
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0051"
down_revision = "0050"
branch_labels = None
depends_on = None

_LEDGER = ("gl_snapshots", "gl_account_balances", "gl_entries")


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE gl_snapshots (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            client_entity_id uuid NOT NULL,
            period_start date NOT NULL,
            period_end date NOT NULL,
            source text NOT NULL CHECK (length(source) BETWEEN 1 AND 100),
            raw_fingerprint text NOT NULL CHECK (raw_fingerprint ~ '^[0-9a-f]{64}$'),
            tb_snapshot_id uuid NOT NULL,
            line_count integer NOT NULL CHECK (line_count > 0),
            total_debit numeric(20, 2) NOT NULL CHECK (total_debit >= 0),
            total_credit numeric(20, 2) NOT NULL CHECK (total_credit >= 0),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            CONSTRAINT gl_snapshots_file
                UNIQUE (tenant_id, client_entity_id, period_start, period_end, raw_fingerprint),
            CONSTRAINT gl_snapshots_balanced CHECK (total_debit = total_credit),
            CONSTRAINT gl_snapshots_period CHECK (period_end >= period_start),
            FOREIGN KEY (tenant_id, client_entity_id) REFERENCES client_entities (tenant_id, id),
            FOREIGN KEY (tenant_id, client_entity_id, tb_snapshot_id)
                REFERENCES ledger_snapshots (tenant_id, client_entity_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE gl_account_balances (
            tenant_id uuid NOT NULL,
            snapshot_id uuid NOT NULL,
            account_code text NOT NULL CHECK (length(account_code) BETWEEN 1 AND 50),
            account_name text NOT NULL CHECK (length(account_name) BETWEEN 1 AND 200),
            opening numeric(20, 2) NOT NULL,
            debit numeric(20, 2) NOT NULL CHECK (debit >= 0),
            credit numeric(20, 2) NOT NULL CHECK (credit >= 0),
            closing numeric(20, 2) NOT NULL,
            tb_closing numeric(20, 2) NOT NULL,
            opening_derived boolean NOT NULL,
            PRIMARY KEY (tenant_id, snapshot_id, account_code),
            CONSTRAINT gl_account_balances_rolls_forward
                CHECK (closing = opening + debit - credit AND closing = tb_closing),
            FOREIGN KEY (tenant_id, snapshot_id) REFERENCES gl_snapshots (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE gl_entries (
            tenant_id uuid NOT NULL,
            snapshot_id uuid NOT NULL,
            line_no integer NOT NULL CHECK (line_no > 0),
            account_code text NOT NULL CHECK (length(account_code) BETWEEN 1 AND 50),
            posted_on date NOT NULL,
            reference text NULL CHECK (length(reference) <= 100),
            kind text NULL CHECK (length(kind) <= 60),
            counterparty text NULL CHECK (length(counterparty) <= 200),
            description text NULL CHECK (length(description) <= 500),
            debit numeric(20, 2) NOT NULL CHECK (debit >= 0),
            credit numeric(20, 2) NOT NULL CHECK (credit >= 0),
            source_ref text NOT NULL CHECK (length(source_ref) BETWEEN 1 AND 40),
            PRIMARY KEY (tenant_id, snapshot_id, line_no),
            FOREIGN KEY (tenant_id, snapshot_id) REFERENCES gl_snapshots (tenant_id, id)
        )
        """
    )
    for table in _LEDGER:
        tenant_table(op, table)
        op.execute(f"REVOKE UPDATE, DELETE ON {table} FROM abacus_app")
        op.execute(
            f"CREATE TRIGGER {table}_no_update_or_delete BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION ledger_immutable()"
        )
        op.execute(
            f"CREATE TRIGGER {table}_no_truncate BEFORE TRUNCATE ON {table} "
            "FOR EACH STATEMENT EXECUTE FUNCTION ledger_immutable()"
        )
    # Balances and entries join a snapshot only in the transaction that created it (ADR-004).
    op.execute(
        """
        CREATE FUNCTION gl_rows_with_snapshot() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM gl_snapshots s
                WHERE s.tenant_id = NEW.tenant_id AND s.id = NEW.snapshot_id
                  AND s.xmin::text::bigint = (txid_current() % 4294967296)
            ) THEN
                RAISE EXCEPTION 'general ledger rows can only be added with their snapshot'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            RETURN NEW;
        END
        $$
        """
    )
    for table in ("gl_account_balances", "gl_entries"):
        op.execute(
            f"CREATE TRIGGER {table}_with_snapshot BEFORE INSERT ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION gl_rows_with_snapshot()"
        )
    insert_columns(
        op,
        "gl_snapshots",
        (
            "id",  # the service sets it, to add balances and entries in the same transaction
            "tenant_id",
            "client_entity_id",
            "period_start",
            "period_end",
            "source",
            "raw_fingerprint",
            "tb_snapshot_id",
            "line_count",
            "total_debit",
            "total_credit",
        ),
    )
    insert_columns(
        op,
        "gl_account_balances",
        (
            "tenant_id",
            "snapshot_id",
            "account_code",
            "account_name",
            "opening",
            "debit",
            "credit",
            "closing",
            "tb_closing",
            "opening_derived",
        ),
    )
    insert_columns(
        op,
        "gl_entries",
        (
            "tenant_id",
            "snapshot_id",
            "line_no",
            "account_code",
            "posted_on",
            "reference",
            "kind",
            "counterparty",
            "description",
            "debit",
            "credit",
            "source_ref",
        ),
    )
    op.execute(
        """
        CREATE TABLE gl_imports (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            client_entity_id uuid NOT NULL,
            format text NOT NULL CHECK (format ~ '^[a-z][a-z0-9_]{0,40}$'),
            period_start date NOT NULL,
            period_end date NOT NULL CHECK (period_end >= period_start),
            storage_key text NOT NULL,
            storage_version_id text NOT NULL,
            fingerprint text NOT NULL CHECK (fingerprint ~ '^[0-9a-f]{64}$'),
            size_bytes integer NOT NULL CHECK (size_bytes > 0),
            status text NOT NULL DEFAULT 'processing'
                CHECK (status IN ('processing', 'waiting_for_tb', 'reconciled', 'failed')),
            failure_code text NULL CHECK (failure_code ~ '^[a-z][a-z_]{0,49}$'),
            failure_details jsonb NULL,
            gl_snapshot_id uuid NULL,
            line_count integer NULL CHECK (line_count >= 0),
            uploaded_by uuid NOT NULL,
            on_behalf boolean NOT NULL DEFAULT false,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, id),
            CONSTRAINT gl_imports_once UNIQUE (tenant_id, client_entity_id, fingerprint),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id),
            FOREIGN KEY (tenant_id, gl_snapshot_id) REFERENCES gl_snapshots (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX gl_imports_waiting ON gl_imports (tenant_id, client_entity_id) "
        "WHERE status = 'waiting_for_tb'"
    )
    tenant_table(op, "gl_imports")
    op.execute("REVOKE DELETE ON gl_imports FROM abacus_app")
    insert_columns(
        op,
        "gl_imports",
        (
            "id",
            "tenant_id",
            "engagement_id",
            "client_entity_id",
            "format",
            "period_start",
            "period_end",
            "storage_key",
            "storage_version_id",
            "fingerprint",
            "size_bytes",
            "uploaded_by",
            "on_behalf",
        ),
    )
    op.execute("REVOKE UPDATE ON gl_imports FROM abacus_app")
    op.execute(
        "GRANT UPDATE (status, failure_code, failure_details, gl_snapshot_id, line_count, "
        "updated_at) ON gl_imports TO abacus_app"
    )


def downgrade() -> None:
    op.execute("DROP TABLE gl_imports")
    for table in ("gl_entries", "gl_account_balances", "gl_snapshots"):
        op.execute(f"DROP TABLE {table}")
    op.execute("DROP FUNCTION gl_rows_with_snapshot()")
