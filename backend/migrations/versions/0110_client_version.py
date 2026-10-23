"""A version on the client record, for CLI-02's edits (P-07-T09; clients contract §3).

`clients.version` starts at 1 and a trigger adds one on every update that changes the row, so a
PATCH names the version it read (`seen_version`) and a stale one is refused (409
`stale_version`). The app never writes the column: it has no UPDATE grant on it, and the trigger
sets it whatever the statement says.

Revision ID: 0110
Revises: 0109
"""

from __future__ import annotations

from alembic import op

revision = "0110"
down_revision = "0109"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE clients ADD COLUMN version integer NOT NULL DEFAULT 1 CHECK (version >= 1)"
    )
    op.execute(
        """
        CREATE FUNCTION clients_bump_version() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            NEW.version := OLD.version;
            IF NEW IS DISTINCT FROM OLD THEN
                NEW.version := OLD.version + 1;
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER clients_bump_version BEFORE UPDATE ON clients "
        "FOR EACH ROW EXECUTE FUNCTION clients_bump_version()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER clients_bump_version ON clients")
    op.execute("DROP FUNCTION clients_bump_version()")
    op.execute("ALTER TABLE clients DROP COLUMN version")
