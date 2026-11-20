"""C-02-T26 (S52; TASK-8808; red): `sync_runs.dataset` admits `vendors` and `vendor_payments`.

QuickBooks vendors (the 1099 flag, a masked tax id) and vendor payments (BillPayment and Purchase
with the payment method) for the CLS-13 1099 / W-9 tracker, read-only (CONN-001 unchanged). The
CHECK list grows; nothing else. Expand-only.

Revision ID: 0991
Revises: 0990
"""

from __future__ import annotations

from alembic import op

revision = "0991"
down_revision = "0990"
branch_labels = None
depends_on = None

_OLD = "('trial_balance', 'prior_trial_balance', 'accounts', 'gl_detail', 'trial_balance_month')"
_NEW = (
    "('trial_balance', 'prior_trial_balance', 'accounts', 'gl_detail', 'trial_balance_month', "
    "'vendors', 'vendor_payments')"
)


def upgrade() -> None:
    op.execute(
        f"ALTER TABLE sync_runs DROP CONSTRAINT sync_runs_dataset_check, "
        f"ADD CONSTRAINT sync_runs_dataset_check CHECK (dataset IN {_NEW})"
    )


def downgrade() -> None:
    # sync_runs are write-once; a downgrade with vendor runs present fails here rather than
    # deleting them.
    op.execute(
        f"ALTER TABLE sync_runs DROP CONSTRAINT sync_runs_dataset_check, "
        f"ADD CONSTRAINT sync_runs_dataset_check CHECK (dataset IN {_OLD})"
    )
