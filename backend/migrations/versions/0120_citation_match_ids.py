"""Citation match ids in C4's grammar (P-03-T06; ADR-166; DEC-219).

Owned by `evidence`.
0109 checked `citations.match_id` against `^[A-Za-z0-9._:-]{1,80}$`, which refuses the formats C4
§3.1 freezes: `ev:<version>#p<page>:<x0>,<top>,<x1>,<bottom>` (`#` and `,`; about 90 characters
with a region), `<file>!<cell>` (`!`) and `ms:<step_key>@<ver>` (`@`). The check now takes those
characters and up to 160 of them. No row changes (none exist before P-03-T06 writes them).

Revision ID: 0120
Revises: 0119
"""

from __future__ import annotations

from alembic import op

revision = "0120"
down_revision = "0119"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE citations DROP CONSTRAINT citations_match_id_check")
    op.execute(
        "ALTER TABLE citations ADD CONSTRAINT citations_match_id_check "
        "CHECK (match_id ~ '^[A-Za-z0-9._:#,!@-]{1,160}$')"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE citations DROP CONSTRAINT citations_match_id_check")
    op.execute(
        "ALTER TABLE citations ADD CONSTRAINT citations_match_id_check "
        "CHECK (match_id ~ '^[A-Za-z0-9._:-]{1,80}$')"
    )
