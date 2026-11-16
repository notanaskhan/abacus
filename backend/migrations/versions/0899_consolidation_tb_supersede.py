"""A-09-T13 (S46; TASK-8094; SPEC-658 AC-1.3): a TB slot can be replaced, expand-only.

Replacing an attached consolidation TB (a new pull, a corrected upload) points the current slot
at its successor and inserts the successor in one transaction. The successor's id is set on the
old row before the new row exists, so the `superseded_by` foreign key becomes DEFERRABLE INITIALLY
DEFERRED (checked at commit); the one-current-slot unique index is unchanged.

Revision ID: 0899
Revises: 0898
"""

from __future__ import annotations

from alembic import op

revision = "0899"
down_revision = "0898"
branch_labels = None
depends_on = None

_FK = "consolidation_trial_balances_tenant_id_superseded_by_fkey"


def upgrade() -> None:
    op.execute(f"ALTER TABLE consolidation_trial_balances DROP CONSTRAINT {_FK}")
    op.execute(
        f"ALTER TABLE consolidation_trial_balances ADD CONSTRAINT {_FK} "
        "FOREIGN KEY (tenant_id, superseded_by) REFERENCES consolidation_trial_balances "
        "(tenant_id, id) DEFERRABLE INITIALLY DEFERRED"
    )


def downgrade() -> None:
    op.execute(f"ALTER TABLE consolidation_trial_balances DROP CONSTRAINT {_FK}")
    op.execute(
        f"ALTER TABLE consolidation_trial_balances ADD CONSTRAINT {_FK} "
        "FOREIGN KEY (tenant_id, superseded_by) REFERENCES consolidation_trial_balances "
        "(tenant_id, id)"
    )
