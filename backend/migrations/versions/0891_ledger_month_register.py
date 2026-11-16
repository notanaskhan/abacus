"""C-01-T17 (S46; TASK-8105; C-01 §4.5; SPEC-655 F5): `ledger_month_register`, expand-only, red.

The hourly ledger sync records a close month as one immutable set: a monthly `ledger_snapshots`
row (`period_kind = 'month'`, C-01-T10), its trial balance lines and `ledger_accounts`, and the
month's register as a general-ledger snapshot tied to it.

- `gl_snapshots.kind` gains `month`: the register of one close month, tied to that month's trial
  balance snapshot (`tb_snapshot_id` required for `year` and `month`, absent for `subsequent`).
- `sync_schedules` gains `retry_at` ("rate limit · retrying 10:07 AM") and `last_failure_code`
  (a safe code, never provider text), which the sync workflow moves with the cursor.

Nothing is updated in place; no existing row changes. Read only: nothing here writes to a client
system (CONN-001, ADR-040).

Revision ID: 0891
Revises: 0890
"""

from __future__ import annotations

from alembic import op

revision = "0891"
down_revision = "0890"
branch_labels = None
depends_on = None

_CODE = "~ '^[a-z][a-z0-9_]{0,63}$'"


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE gl_snapshots
            DROP CONSTRAINT gl_snapshots_kind_check,
            ADD CONSTRAINT gl_snapshots_kind_check
                CHECK (kind IN ('year', 'subsequent', 'month')),
            DROP CONSTRAINT gl_snapshots_tb_for_year,
            ADD CONSTRAINT gl_snapshots_tb_for_year
                CHECK ((kind IN ('year', 'month')) = (tb_snapshot_id IS NOT NULL))
        """
    )
    op.execute(
        f"""
        ALTER TABLE sync_schedules
            ADD COLUMN retry_at timestamptz NULL,
            ADD COLUMN last_failure_code text NULL
                CONSTRAINT sync_schedules_failure_code CHECK (last_failure_code {_CODE})
        """
    )
    op.execute("GRANT UPDATE (retry_at, last_failure_code) ON sync_schedules TO abacus_app")


def downgrade() -> None:
    op.execute("REVOKE UPDATE (retry_at, last_failure_code) ON sync_schedules FROM abacus_app")
    op.execute("ALTER TABLE sync_schedules DROP COLUMN last_failure_code, DROP COLUMN retry_at")
    op.execute(
        """
        ALTER TABLE gl_snapshots
            DROP CONSTRAINT gl_snapshots_tb_for_year,
            ADD CONSTRAINT gl_snapshots_tb_for_year
                CHECK ((kind = 'year') = (tb_snapshot_id IS NOT NULL)),
            DROP CONSTRAINT gl_snapshots_kind_check,
            ADD CONSTRAINT gl_snapshots_kind_check CHECK (kind IN ('year', 'subsequent'))
        """
    )
