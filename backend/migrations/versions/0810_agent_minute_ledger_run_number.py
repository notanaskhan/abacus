"""The agent-minute ledger names each run's number (P-10-T42; TASK-6801; DEC-3401; P-10 §3.10).

ENG-06 lists an engagement's runs by number ("Run #4019 · PBC list builder · 46 agent-min"). The
ledger is insert-only and the platform module never reads `agent_runs` (ADR-008), so the number
travels on `agent_run.completed` and is stored with the minutes. Null for a run with no number
(a legacy run).

Expand-only; the downgrade drops the column.

Revision ID: 0810
Revises: 0802
"""

from __future__ import annotations

from alembic import op

revision = "0810"
down_revision = "0802"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE agent_minute_ledger ADD COLUMN run_number bigint NULL CHECK (run_number > 0)"
    )
    op.execute("GRANT INSERT (run_number) ON agent_minute_ledger TO abacus_app")


def downgrade() -> None:
    op.execute("ALTER TABLE agent_minute_ledger DROP COLUMN run_number")
