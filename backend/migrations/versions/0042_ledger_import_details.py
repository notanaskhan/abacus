"""What a failed ledger import found (SPEC-028 §4.8; TASK-053 D1).

- `ledger_imports.difference`: debits minus credits when the export doesn't balance.
- `ledger_imports.found_period_end`: the period end the export covers when it isn't the
  engagement's.

Both are computed by code from the parsed lines (ADR-050) and shown through fixed message
templates (ADR-111), to the client at once and to the firm on the latest import.

Revision ID: 0042
Revises: 0041
"""

from __future__ import annotations

from alembic import op

revision = "0042"
down_revision = "0041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE ledger_imports "
        "ADD COLUMN difference numeric(20, 2) NULL CHECK (difference <> 0), "
        "ADD COLUMN found_period_end date NULL"
    )
    op.execute("GRANT INSERT (difference, found_period_end) ON ledger_imports TO abacus_app")


def downgrade() -> None:
    op.execute("REVOKE INSERT (difference, found_period_end) ON ledger_imports FROM abacus_app")
    op.execute("ALTER TABLE ledger_imports DROP COLUMN difference, DROP COLUMN found_period_end")
