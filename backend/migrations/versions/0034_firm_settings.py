"""Firm settings for autonomy and onboarding (SPEC-024 AC-5, AC-7; TASK-042).

The firm's autonomy level (ADR-061; new firms start at Routine, 1) and when it was chosen; the
onboarding steps a firm administrator acknowledges (budget reviewed, no walls needed, SSO
skipped) and the checklist's dismissal. The app may update exactly these columns of its own
firm (forced RLS); nothing else on `firms` changes.

Revision ID: 0034
Revises: 0033
"""

from __future__ import annotations

from alembic import op

revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None

_COLUMNS = (
    "autonomy_level, autonomy_set_at, budget_reviewed_at, walls_none_needed_at, "
    "sso_skipped_at, onboarding_dismissed_at"
)


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE firms
            ADD COLUMN autonomy_level smallint NOT NULL DEFAULT 1
                CHECK (autonomy_level BETWEEN 0 AND 3),
            ADD COLUMN autonomy_set_at timestamptz NULL,
            ADD COLUMN budget_reviewed_at timestamptz NULL,
            ADD COLUMN walls_none_needed_at timestamptz NULL,
            ADD COLUMN sso_skipped_at timestamptz NULL,
            ADD COLUMN onboarding_dismissed_at timestamptz NULL
        """
    )
    op.execute(f"GRANT UPDATE ({_COLUMNS}) ON firms TO abacus_app")


def downgrade() -> None:
    op.execute(f"REVOKE UPDATE ({_COLUMNS}) ON firms FROM abacus_app")
    op.execute(
        "ALTER TABLE firms DROP COLUMN onboarding_dismissed_at, DROP COLUMN sso_skipped_at, "
        "DROP COLUMN walls_none_needed_at, DROP COLUMN budget_reviewed_at, "
        "DROP COLUMN autonomy_set_at, DROP COLUMN autonomy_level"
    )
