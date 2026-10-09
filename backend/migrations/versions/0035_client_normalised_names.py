"""Normalised client and entity names (SPEC-025 AC-1; TASK-043 D2).

A new engagement picks a client the firm already has; a likely duplicate is caught by its
normalised name: lower case, punctuation as spaces, common legal suffixes dropped, spaces
collapsed. `organisations.normalise` does the same in Python (kept in step by a unit test). An
entity can't be added twice to one client.

Revision ID: 0035
Revises: 0034
"""

from __future__ import annotations

from alembic import op

revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None

# Lower case; anything but letters and digits becomes a space; legal suffixes go; spaces collapse.
_NORMALISED = (
    "btrim(regexp_replace(regexp_replace(regexp_replace(lower(name), '[^a-z0-9]+', ' ', 'g'), "
    "'\\m(inc|incorporated|llc|ltd|limited|corp|corporation|co|company|plc|lp|llp|pc|pllc)\\M',"
    " ' ', 'g'), '\\s+', ' ', 'g'))"
)


def upgrade() -> None:
    for table in ("clients", "client_entities"):
        op.execute(
            f"ALTER TABLE {table} ADD COLUMN normalised_name text "
            f"GENERATED ALWAYS AS ({_NORMALISED}) STORED"
        )
    op.execute("CREATE INDEX clients_normalised_name ON clients (tenant_id, normalised_name)")
    op.execute(
        "CREATE UNIQUE INDEX client_entities_one_name ON client_entities "
        "(tenant_id, client_id, normalised_name)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX client_entities_one_name")
    op.execute("DROP INDEX clients_normalised_name")
    for table in ("client_entities", "clients"):
        op.execute(f"ALTER TABLE {table} DROP COLUMN normalised_name")
