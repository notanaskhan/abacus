"""I-02-T13 (S42; TASK-7913; I-02 §4.4; DEC-4916): a claimed briefing row records its facts hash
when its run lands, expand-only.

`ensure_briefings` claims a `building` row per (viewer, engagement, day) before it starts the
run, so two concurrent first opens start one run. When the run's step finishes it completes that
same row (status, blocks, run, built time and now the facts hash it was built from), which needs
`facts_hash` among the app role's updatable columns. A terminal row stays immutable (0851's
trigger).

Revision ID: 0871
Revises: 0870
"""

from __future__ import annotations

from alembic import op

revision = "0871"
down_revision = "0870"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("GRANT UPDATE (facts_hash) ON daily_briefings TO abacus_app")


def downgrade() -> None:
    op.execute("REVOKE UPDATE (facts_hash) ON daily_briefings FROM abacus_app")
