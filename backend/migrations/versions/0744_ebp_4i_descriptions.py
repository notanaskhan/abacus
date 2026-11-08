"""A-05-T58 remainder (S31; TASK-6233; DEC-2828): the facts Schedule H line 4i's column (c) reads.

Expand-only: `ebp_trust_report_lines.description` (the trust report's own words for a holding,
such as "registered investment company") and `ebp_participant_loans.interest_rate` (a percent),
both nullable, with the app role's INSERT on them. Code composes the loans' description from the
rates and the latest maturity; a holding's description is the trust report's, never a guess.

Revision ID: 0744
Revises: 0743
"""

from __future__ import annotations

from alembic import op

revision = "0744"
down_revision = "0743"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE ebp_trust_report_lines ADD COLUMN description text NULL "
        "CHECK (char_length(description) BETWEEN 1 AND 200)"
    )
    op.execute(
        "ALTER TABLE ebp_participant_loans ADD COLUMN interest_rate numeric(7, 4) NULL "
        "CHECK (interest_rate >= 0 AND interest_rate <= 100)"
    )
    op.execute("GRANT INSERT (description) ON ebp_trust_report_lines TO abacus_app")
    op.execute("GRANT INSERT (interest_rate) ON ebp_participant_loans TO abacus_app")


def downgrade() -> None:
    op.execute("REVOKE INSERT (interest_rate) ON ebp_participant_loans FROM abacus_app")
    op.execute("REVOKE INSERT (description) ON ebp_trust_report_lines FROM abacus_app")
    op.execute("ALTER TABLE ebp_participant_loans DROP COLUMN interest_rate")
    op.execute("ALTER TABLE ebp_trust_report_lines DROP COLUMN description")
