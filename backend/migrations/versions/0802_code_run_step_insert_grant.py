"""S35 round 2 end pass (TASK-6740): two column grants the A-07 paths needed on Postgres, found by
A-07-T41's archive scenario (the first load to run them against a database). A code run
(A-07-T32) records each step finished in its insert, so the app role may insert `started_at`,
`ended_at`, `records_read` and `outputs_summary` on `agent_run_steps`; a report choice
(A-07-T27) moves the report to the newest published template, so it may update
`audit_reports.template_id`. Expand only: grants, no data.

Revision ID: 0802
Revises: 0801
"""

from __future__ import annotations

from alembic import op

revision = "0802"
down_revision = "0801"
branch_labels = None
depends_on = None

_COLUMNS = "started_at, ended_at, records_read, outputs_summary"


def upgrade() -> None:
    op.execute(f"GRANT INSERT ({_COLUMNS}) ON agent_run_steps TO abacus_app")
    op.execute("GRANT UPDATE (template_id) ON audit_reports TO abacus_app")


def downgrade() -> None:
    op.execute("REVOKE UPDATE (template_id) ON audit_reports FROM abacus_app")
    op.execute(f"REVOKE INSERT ({_COLUMNS}) ON agent_run_steps FROM abacus_app")
