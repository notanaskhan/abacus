"""Teams of kind `intake` (N-01-T08; N-01 §4.2 "T08"; DEC-20, P-10; DEC-819).

The intake scope is a firm-level team: its members read unmatched inbox threads by sender and
subject, and an attachment's content until it is filed (DEC-75). `teams.kind` gains `intake`.
The downgrade refuses while an intake team exists (it would otherwise break the old CHECK).

Revision ID: 0295
Revises: 0294
"""

from __future__ import annotations

from alembic import op

revision = "0295"
down_revision = "0294"
branch_labels = None
depends_on = None

_BEFORE = (
    "('service_line', 'practice_group', 'eqr_pool', 'monitoring_reviewers', 'reviewer_pool', "
    "'custom')"
)
_AFTER = (
    "('service_line', 'practice_group', 'eqr_pool', 'monitoring_reviewers', 'reviewer_pool', "
    "'custom', 'intake')"
)


def upgrade() -> None:
    op.execute(
        "ALTER TABLE teams DROP CONSTRAINT teams_kind_check, "
        f"ADD CONSTRAINT teams_kind_check CHECK (kind IN {_AFTER})"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE teams DROP CONSTRAINT teams_kind_check, "
        f"ADD CONSTRAINT teams_kind_check CHECK (kind IN {_BEFORE})"
    )
