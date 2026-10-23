"""A request's client wording is editable before it is closed (P-06-T10; SHL-14 b).

`request_items.description` was insert-only for the app; the lifecycle's PATCH edits it on any
non-terminal request (the service refuses Received and Not applicable). An edit is audited by
field name, never its text. A model-drafted wording keeps its fingerprint, so an unchanged one is
still refused at send while P-25 is off (DV-11).

Revision ID: 0113
Revises: 0112
"""

from __future__ import annotations

from alembic import op

revision = "0113"
down_revision = "0112"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("GRANT UPDATE (description) ON request_items TO abacus_app")


def downgrade() -> None:
    op.execute("REVOKE UPDATE (description) ON request_items FROM abacus_app")
