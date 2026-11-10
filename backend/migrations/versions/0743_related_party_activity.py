"""A-05-T57 close (S31; TASK-6232; DEC-2827): a related party's year activity and its disclosure.

Expand-only: three columns on `related_parties`, and the app role's INSERT and UPDATE on them.
`transactions` is what the entity did with the party in the year, as a person recorded it (the
shape of 0685's `parties_in_interest.transactions`: a description and an optional amount);
`disclosure` is the person's words for where the party is disclosed, and `disclosure_note` says
those words name a note in the financial statements (AUD-20).

Revision ID: 0743
Revises: 0742
"""

from __future__ import annotations

from alembic import op

revision = "0743"
down_revision = "0742"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE related_parties "
        "ADD COLUMN transactions jsonb NOT NULL DEFAULT '[]'::jsonb "
        "CHECK (jsonb_typeof(transactions) = 'array' AND jsonb_array_length(transactions) <= 50), "
        "ADD COLUMN disclosure text NULL CHECK (char_length(disclosure) BETWEEN 1 AND 300), "
        "ADD COLUMN disclosure_note boolean NOT NULL DEFAULT false, "
        "ADD CONSTRAINT related_parties_disclosure_note "
        "CHECK (NOT disclosure_note OR disclosure IS NOT NULL)"
    )
    op.execute(
        "GRANT INSERT (transactions, disclosure, disclosure_note), "
        "UPDATE (transactions, disclosure, disclosure_note) ON related_parties TO abacus_app"
    )


def downgrade() -> None:
    op.execute(
        "REVOKE INSERT (transactions, disclosure, disclosure_note), "
        "UPDATE (transactions, disclosure, disclosure_note) ON related_parties FROM abacus_app"
    )
    op.execute(
        "ALTER TABLE related_parties DROP CONSTRAINT related_parties_disclosure_note, "
        "DROP COLUMN disclosure_note, DROP COLUMN disclosure, DROP COLUMN transactions"
    )
