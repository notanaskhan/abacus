"""An exception for resolution carries no COSO component yet (A-04-T28; AUD-09 a; DEC-2224).
Expand-only.

AUD-09's sheet shows "—" for the three exceptions still for resolution (cutoff, auto-enrolment,
loan offsets): the COSO component is part of grading a deficiency, not of recording an
exception. 0657 made `control_exceptions.coso_component` NOT NULL; this drops that. The CHECK on
its values stays (NULL passes it). The downgrade restores NOT NULL and is refused while any row
has no component.

Revision ID: 0663
Revises: 0662
"""

from __future__ import annotations

from alembic import op

revision = "0663"
down_revision = "0662"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE control_exceptions ALTER COLUMN coso_component DROP NOT NULL")


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM control_exceptions WHERE coso_component IS NULL) THEN
                RAISE EXCEPTION 'control_exceptions rows without a COSO component exist';
            END IF;
        END $$
        """
    )
    op.execute("ALTER TABLE control_exceptions ALTER COLUMN coso_component SET NOT NULL")
