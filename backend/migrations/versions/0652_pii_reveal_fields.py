"""A-05-T18 (A-05 §4.10; DEC-1858; DEC-2067): a reveal of a sealed field, not only a page region.
Expand only.

`pii_reveals` (0109) records P-03's region reveals; a census participant's SSN or date of birth is
a sealed field on its record, with no evidence region. The table gains `field_ref`
(`ebp_participant:<id>:ssn|dob`), and a reveal names either a region and its evidence version
(P-03, unchanged) or a field. Every other rule stays: a person only (`actor_kind = 'human'`),
insert-only, the hourly count read from this table.

Revision ID: 0652
Revises: 0651
"""

from __future__ import annotations

from alembic import op

revision = "0652"
down_revision = "0651"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE pii_reveals ADD COLUMN field_ref text NULL "
        "CHECK (field_ref ~ '^[a-z][a-z_]{0,39}:[0-9a-f-]{36}:[a-z_]{1,20}$')"
    )
    op.execute("ALTER TABLE pii_reveals ALTER COLUMN region_id DROP NOT NULL")
    op.execute("ALTER TABLE pii_reveals ALTER COLUMN evidence_version_id DROP NOT NULL")
    op.execute(
        "ALTER TABLE pii_reveals ADD CONSTRAINT pii_reveals_region_or_field CHECK ("
        "(region_id IS NOT NULL AND evidence_version_id IS NOT NULL AND field_ref IS NULL) "
        "OR (region_id IS NULL AND evidence_version_id IS NULL AND field_ref IS NOT NULL))"
    )


def downgrade() -> None:
    # pii_reveals is insert-only (0109's trigger): a field reveal cannot be dropped, so a
    # downgrade past one is refused rather than losing the record.
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pii_reveals WHERE field_ref IS NOT NULL) THEN "
        "RAISE EXCEPTION 'pii_reveals holds field reveals; downgrade refused'; END IF; END $$"
    )
    op.execute("ALTER TABLE pii_reveals DROP CONSTRAINT pii_reveals_region_or_field")
    op.execute("ALTER TABLE pii_reveals ALTER COLUMN evidence_version_id SET NOT NULL")
    op.execute("ALTER TABLE pii_reveals ALTER COLUMN region_id SET NOT NULL")
    op.execute("ALTER TABLE pii_reveals DROP COLUMN field_ref")
