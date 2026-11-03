"""C7 additive: an envelope document may be a page range of a version (N-04-T08; N-04 §4.2,
NOT-03 c; DEC-2205; expand-only).

NOT-03's response page is one page of the generated response letter (the CP2000 response page
the taxpayers sign), so `envelope_documents` gains `page_from` and `page_to`: both or neither,
1 ≤ from ≤ to, and only together with `page_count` covering them. Existing rows are whole
documents (both null).

Revision ID: 0656
Revises: 0655
"""

from __future__ import annotations

from alembic import op

revision = "0656"
down_revision = "0655"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE envelope_documents
            ADD COLUMN page_from smallint NULL CHECK (page_from BETWEEN 1 AND 2000),
            ADD COLUMN page_to smallint NULL CHECK (page_to BETWEEN 1 AND 2000),
            ADD CONSTRAINT envelope_documents_page_range CHECK (
                (page_from IS NULL AND page_to IS NULL)
                OR (page_from IS NOT NULL AND page_to IS NOT NULL AND page_from <= page_to
                    AND (page_count IS NULL OR page_to <= page_count))
            )
        """
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE envelope_documents DROP CONSTRAINT envelope_documents_page_range, "
        "DROP COLUMN page_from, DROP COLUMN page_to"
    )
