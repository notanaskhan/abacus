"""The group audit's work item flag (A-09-T30; A-09 §3.1; ENG-03 g; DEC-5408).

ENG-03 g's "Group audit" toggle makes the engagement's assurance work item a group audit:
`assurance_work_items.is_group_audit` (0068) becomes writable by the app role, set once by the
engagement's creation under the `group_audit` capability. The component entities are
`engagement_entities` rows with role `component` (0068 already allows the role).

Revision ID: 0946
Revises: 0945
"""

from __future__ import annotations

from alembic import op

revision = "0946"
down_revision = "0945"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("GRANT UPDATE (is_group_audit) ON assurance_work_items TO abacus_app")


def downgrade() -> None:
    op.execute("REVOKE UPDATE (is_group_audit) ON assurance_work_items FROM abacus_app")
