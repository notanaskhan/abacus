"""The word layer object's size (P-03-T05; ADR-104; DEC-217).

Owned by `evidence`.
`evidence_pages` (0109) records a page's sealed layer object by key, storage version and
fingerprint, but storage opens an object only against its recorded size too, so a page row could
not be read back. `text_layer_size` is that size: present exactly when the page has a layer
object. Expand-only: no rows exist before P-03-T05 writes them.

Revision ID: 0119
Revises: 0115
"""

from __future__ import annotations

from alembic import op

revision = "0119"
down_revision = "0115"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE evidence_pages ADD COLUMN text_layer_size integer NULL "
        "CHECK (text_layer_size >= 0), "
        "ADD CONSTRAINT evidence_pages_layer_size "
        "CHECK ((text_layer_key IS NULL) = (text_layer_size IS NULL))"
    )
    op.execute("GRANT INSERT (text_layer_size) ON evidence_pages TO abacus_app")


def downgrade() -> None:
    op.execute("ALTER TABLE evidence_pages DROP COLUMN text_layer_size")
