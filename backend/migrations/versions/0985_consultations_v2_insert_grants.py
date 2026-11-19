"""Q-05-T09 (S51 partials, TASK-8729; DEC-5723): the application role may insert the two columns
0983 added for a new consultation, `facts_sealed` (AUD-28 f's facts) and `consulted_role`
(partner, specialist or national), so the create route can write them. 0983 widened the table
but kept 0644's insert grant.

Revision ID: 0985
Revises: 0984
"""

from __future__ import annotations

from alembic import op

revision = "0985"
down_revision = "0984"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE consultations ADD CONSTRAINT consultations_consulted_role_known "
        "CHECK (consulted_role IS NULL OR consulted_role IN ('partner', 'specialist', 'national'))"
    )
    op.execute("GRANT INSERT (facts_sealed, consulted_role) ON consultations TO abacus_app")


def downgrade() -> None:
    op.execute("REVOKE INSERT (facts_sealed, consulted_role) ON consultations FROM abacus_app")
    op.execute("ALTER TABLE consultations DROP CONSTRAINT consultations_consulted_role_known")
