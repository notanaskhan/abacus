"""The search for unrecorded liabilities (SPEC-038; TASK-086, TASK-087).

- `gl_snapshots.kind` (`year` or `subsequent`): a subsequent-period ledger has no trial balance
  (`tb_snapshot_id` null only for it); `gl_imports.kind` likewise. Year readers filter `year`.
- `engagement_accounts` (insert-only; the newest per role is current): bank and payables accounts
  confirmed by a person.
- `procedures.definition` allows `unrecorded_liabilities`.
- `selected_items`: a payment's band and the year-end ledger's matching bill, if any.
- `item_results.relates_to_year` (`yes`, `no`, `unclear`).

Revision ID: 0060
Revises: 0059
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0060"
down_revision = "0059"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE gl_snapshots ADD COLUMN kind text NOT NULL DEFAULT 'year' "
        "CHECK (kind IN ('year', 'subsequent')), ALTER COLUMN tb_snapshot_id DROP NOT NULL, "
        "ADD CONSTRAINT gl_snapshots_tb_for_year CHECK "
        "((kind = 'year') = (tb_snapshot_id IS NOT NULL))"
    )
    op.execute("GRANT INSERT (kind) ON gl_snapshots TO abacus_app")
    op.execute(
        "ALTER TABLE gl_imports ADD COLUMN kind text NOT NULL DEFAULT 'year' "
        "CHECK (kind IN ('year', 'subsequent'))"
    )
    op.execute("GRANT INSERT (kind) ON gl_imports TO abacus_app")
    op.execute(
        """
        CREATE TABLE engagement_accounts (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            role text NOT NULL CHECK (role IN ('bank', 'payables')),
            account_codes text[] NOT NULL CHECK (cardinality(account_codes) BETWEEN 1 AND 50),
            confirmed_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id)
        )
        """
    )
    tenant_table(op, "engagement_accounts")
    op.execute("REVOKE UPDATE, DELETE ON engagement_accounts FROM abacus_app")
    insert_columns(
        op,
        "engagement_accounts",
        ("tenant_id", "engagement_id", "role", "account_codes", "confirmed_by"),
    )
    op.execute("ALTER TABLE procedures DROP CONSTRAINT procedures_definition_check")
    op.execute(
        "ALTER TABLE procedures ADD CONSTRAINT procedures_definition_check CHECK "
        "(definition IN ('journal_entry_testing', 'unrecorded_liabilities'))"
    )
    op.execute(
        "ALTER TABLE selected_items ADD COLUMN band integer NULL CHECK (band >= 1), "
        "ADD COLUMN recorded_bill_reference text NULL, "
        "ADD COLUMN recorded_bill_date date NULL"
    )
    op.execute(
        "GRANT INSERT (band, recorded_bill_reference, recorded_bill_date) "
        "ON selected_items TO abacus_app"
    )
    op.execute(
        "ALTER TABLE item_results ADD COLUMN relates_to_year text NULL "
        "CHECK (relates_to_year IN ('yes', 'no', 'unclear'))"
    )
    op.execute("GRANT INSERT (relates_to_year) ON item_results TO abacus_app")


def downgrade() -> None:
    op.execute("REVOKE INSERT (relates_to_year) ON item_results FROM abacus_app")
    op.execute("ALTER TABLE item_results DROP COLUMN relates_to_year")
    op.execute(
        "REVOKE INSERT (band, recorded_bill_reference, recorded_bill_date) "
        "ON selected_items FROM abacus_app"
    )
    op.execute(
        "ALTER TABLE selected_items DROP COLUMN band, DROP COLUMN recorded_bill_reference, "
        "DROP COLUMN recorded_bill_date"
    )
    op.execute("ALTER TABLE procedures DROP CONSTRAINT procedures_definition_check")
    op.execute(
        "ALTER TABLE procedures ADD CONSTRAINT procedures_definition_check CHECK "
        "(definition IN ('journal_entry_testing'))"
    )
    op.execute("DROP TABLE engagement_accounts")
    op.execute("REVOKE INSERT (kind) ON gl_imports FROM abacus_app")
    op.execute("ALTER TABLE gl_imports DROP COLUMN kind")
    op.execute("REVOKE INSERT (kind) ON gl_snapshots FROM abacus_app")
    op.execute(
        "ALTER TABLE gl_snapshots DROP CONSTRAINT gl_snapshots_tb_for_year, DROP COLUMN kind, "
        "ALTER COLUMN tb_snapshot_id SET NOT NULL"
    )
