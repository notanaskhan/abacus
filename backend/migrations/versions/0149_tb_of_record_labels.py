"""The trial balance of record, labels on snapshots (A-02-T04; TASK-1187; SPEC-333 AC-32 to AC-34).

`trial_balances` and the insert-only, human-only `trial_balance_versions` exist since 0073
(SPEC-309); this migration adds what A-02 §4.2 T04 asks for beyond them.

- `ledger_snapshots.label` (`standard`, `interim`, `prior`, `budget`, `preliminary`; default
  `standard`). The app may supply it on insert. Adding a column with a constant default changes
  no row: Postgres records the default in the catalogue, and no DML runs, so the ADR-004
  triggers never fire and no snapshot is updated.
- `ledger_snapshots.source_kind`, generated and stored from `source` (`import_%` is `import`,
  `fake` is `fake`, anything else `connector`). P-58 widens the expression for
  `document_extraction` (A-05). A stored generated column rewrites the table without DML; no
  role can insert or update it.
- The second immutability layer on `trial_balance_versions` (ADR-004): BEFORE UPDATE OR DELETE
  and BEFORE TRUNCATE triggers calling `ledger_immutable()`, as for `ledger_snapshots`. 0073 only
  revoked UPDATE and DELETE from the app (ED-037).

Downgrade refuses while any snapshot carries a label other than `standard` (it would be lost).

Revision ID: 0149
Revises: 0146
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns

revision = "0149"
down_revision = "0146"
branch_labels = None
depends_on = None

_SNAPSHOT_INSERTS = (
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
)


def upgrade() -> None:
    op.execute(
        "ALTER TABLE ledger_snapshots ADD COLUMN label text NOT NULL DEFAULT 'standard' "
        "CONSTRAINT ledger_snapshots_label "
        "CHECK (label IN ('standard', 'interim', 'prior', 'budget', 'preliminary'))"
    )
    op.execute(
        r"""
        ALTER TABLE ledger_snapshots ADD COLUMN source_kind text
            GENERATED ALWAYS AS (
                CASE
                    WHEN source LIKE 'import\_%' THEN 'import'
                    WHEN source = 'fake' THEN 'fake'
                    ELSE 'connector'
                END
            ) STORED
        """
    )
    insert_columns(op, "ledger_snapshots", (*_SNAPSHOT_INSERTS, "label"))
    op.execute(
        "CREATE TRIGGER trial_balance_versions_no_update_or_delete "
        "BEFORE UPDATE OR DELETE ON trial_balance_versions "
        "FOR EACH ROW EXECUTE FUNCTION ledger_immutable()"
    )
    op.execute(
        "CREATE TRIGGER trial_balance_versions_no_truncate "
        "BEFORE TRUNCATE ON trial_balance_versions "
        "FOR EACH STATEMENT EXECUTE FUNCTION ledger_immutable()"
    )


def downgrade() -> None:
    # Forced row-level security hides every row from the owner here (no tenant is set): lift
    # FORCE for this transaction only to look, then put it back (0009's pattern).
    op.execute("ALTER TABLE ledger_snapshots NO FORCE ROW LEVEL SECURITY")
    op.execute(
        "DO $$ BEGIN "
        "IF EXISTS (SELECT 1 FROM ledger_snapshots WHERE label <> 'standard') "
        "THEN RAISE EXCEPTION 'refusing to downgrade 0149: a ledger snapshot carries a label "
        "other than standard (ADR-004)'; "
        "END IF; END $$"
    )
    op.execute("ALTER TABLE ledger_snapshots FORCE ROW LEVEL SECURITY")
    op.execute("DROP TRIGGER trial_balance_versions_no_truncate ON trial_balance_versions")
    op.execute("DROP TRIGGER trial_balance_versions_no_update_or_delete ON trial_balance_versions")
    op.execute("ALTER TABLE ledger_snapshots DROP COLUMN source_kind")
    op.execute("ALTER TABLE ledger_snapshots DROP COLUMN label")
    insert_columns(op, "ledger_snapshots", _SNAPSHOT_INSERTS)
