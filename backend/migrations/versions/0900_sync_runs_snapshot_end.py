"""C-01-T17 (S46; TASK-8097; DEC-5071): a run no request item asked for ends at its snapshot.

`sync_runs_succeeded_complete` (0009) required an evidence version on every succeeded run. Only a
request-item run renders one: an on-demand pull (A-02-T30, `on-demand-pulls`) and the hourly
ledger sync (C-01-T17, `schedule`) end at the snapshot, which AUD-06 and the close adopt. The
check now asks for evidence only when `trigger = 'request_item'`; the raw fingerprint and the
snapshot stay required for every succeeded run. Expand-only.

Revision ID: 0900
Revises: 0899
"""

from __future__ import annotations

from alembic import op

revision = "0900"
down_revision = "0899"
branch_labels = None
depends_on = None

_CHECK = "sync_runs_succeeded_complete"


def upgrade() -> None:
    op.execute(f"ALTER TABLE sync_runs DROP CONSTRAINT {_CHECK}")
    op.execute(
        f"ALTER TABLE sync_runs ADD CONSTRAINT {_CHECK} CHECK ("
        "status <> 'succeeded' OR (raw_fingerprint IS NOT NULL AND snapshot_id IS NOT NULL "
        "AND (evidence_version_id IS NOT NULL OR trigger <> 'request_item')))"
    )


def downgrade() -> None:
    op.execute(f"ALTER TABLE sync_runs DROP CONSTRAINT {_CHECK}")
    # NOT VALID: runs that ended at their snapshot stay; new rows are checked as before.
    op.execute(
        f"ALTER TABLE sync_runs ADD CONSTRAINT {_CHECK} CHECK ("
        "status <> 'succeeded' OR (raw_fingerprint IS NOT NULL AND snapshot_id IS NOT NULL "
        "AND evidence_version_id IS NOT NULL)) NOT VALID"
    )
