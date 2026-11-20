"""S52 end pass (TASK-8860; Q-05-T09 follow-up; AUD-28): `consultation_links.target_kind` admits
`decision_card`, so a consultation names the decision card it informed (AUD-28's "Linked
decision" pane, read-only SHL-11). The CHECK list grows; nothing else. Expand-only.

Revision ID: 1002
Revises: 1001
"""

from __future__ import annotations

from alembic import op

revision = "1002"
down_revision = "1001"
branch_labels = None
depends_on = None

_OLD = "('finding', 'issue', 'document', 'workpaper', 'post_issuance_case')"
_NEW = "('finding', 'issue', 'document', 'workpaper', 'post_issuance_case', 'decision_card')"


def upgrade() -> None:
    op.execute(
        f"ALTER TABLE consultation_links DROP CONSTRAINT consultation_links_target_kind_check, "
        f"ADD CONSTRAINT consultation_links_target_kind_check CHECK (target_kind IN {_NEW})"
    )


def downgrade() -> None:
    # links are the record of what a consultation informed; a downgrade with decision-card links
    # present fails here rather than deleting them.
    op.execute(
        f"ALTER TABLE consultation_links DROP CONSTRAINT consultation_links_target_kind_check, "
        f"ADD CONSTRAINT consultation_links_target_kind_check CHECK (target_kind IN {_OLD})"
    )
