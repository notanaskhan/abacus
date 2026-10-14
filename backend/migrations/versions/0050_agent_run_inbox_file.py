"""Agent runs on inbox files (SPEC-033; TASK-066).

`agent_runs.inbox_file_id`: the inbox file a matcher run concerns, so the firm sees a run in
progress or failed (for example `data_boundary`) beside its file, not only completed proposals.

Revision ID: 0050
Revises: 0049
"""

from __future__ import annotations

from alembic import op

revision = "0050"
down_revision = "0049"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE agent_runs ADD COLUMN inbox_file_id uuid NULL")
    op.execute(
        "ALTER TABLE agent_runs ADD CONSTRAINT agent_runs_inbox_file "
        "FOREIGN KEY (tenant_id, inbox_file_id) REFERENCES inbox_files (tenant_id, id)"
    )
    op.execute(
        "CREATE INDEX agent_runs_by_inbox_file ON agent_runs (tenant_id, inbox_file_id) "
        "WHERE inbox_file_id IS NOT NULL"
    )
    op.execute("GRANT INSERT (inbox_file_id) ON agent_runs TO abacus_app")


def downgrade() -> None:
    op.execute("REVOKE INSERT (inbox_file_id) ON agent_runs FROM abacus_app")
    op.execute("DROP INDEX agent_runs_by_inbox_file")
    op.execute("ALTER TABLE agent_runs DROP CONSTRAINT agent_runs_inbox_file")
    op.execute("ALTER TABLE agent_runs DROP COLUMN inbox_file_id")
