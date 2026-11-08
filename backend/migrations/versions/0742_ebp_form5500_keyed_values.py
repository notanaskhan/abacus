"""A-05-T58 close (S31; TASK-6225; DEC-2820): a keyed Form 5500 value keeps who keyed it and its
citation note.

Expand-only: two nullable columns on `ebp_form5500_lines` (the person, and the citation note
sealed like every Restricted note), set together, and the app role's UPDATE on them. A keyed value
is the agent-off path of DV-EBP-07-1: the value a person reads off the draft, with where they
read it.

Revision ID: 0742
Revises: 0741
"""

from __future__ import annotations

from alembic import op

revision = "0742"
down_revision = "0741"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE ebp_form5500_lines ADD COLUMN keyed_by uuid NULL, "
        "ADD COLUMN keyed_note_sealed bytea NULL "
        "CHECK (octet_length(keyed_note_sealed) <= 4096), "
        "ADD CONSTRAINT ebp_form5500_lines_keyed_together "
        "CHECK ((keyed_by IS NULL) = (keyed_note_sealed IS NULL))"
    )
    op.execute("GRANT UPDATE (keyed_by, keyed_note_sealed) ON ebp_form5500_lines TO abacus_app")


def downgrade() -> None:
    op.execute("REVOKE UPDATE (keyed_by, keyed_note_sealed) ON ebp_form5500_lines FROM abacus_app")
    op.execute(
        "ALTER TABLE ebp_form5500_lines DROP CONSTRAINT ebp_form5500_lines_keyed_together, "
        "DROP COLUMN keyed_note_sealed, DROP COLUMN keyed_by"
    )
