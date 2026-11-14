"""P-03 reveal window (TASK-7958; P-03 §4.2; DEC-4948): a reveal lasts its whole seconds, red.

`pii_reveals.revealed_at` is the server's (`DEFAULT clock_timestamp()`; the app role may not
insert it, migration 0109) and `expires_at` is the app's `clock_timestamp() + :expires`. Two
clock reads in one INSERT land microseconds apart, so a 30 s reveal could last 30.000001 s
(P-03-T18's AC-26 assertion flaked on it). A BEFORE INSERT trigger rounds the window to whole
seconds from the server's own `revealed_at`; the app still cannot set either time freely.

Expand-only: a trigger function and one trigger. Downgrade drops both.

Revision ID: 0884
Revises: 0883
"""

from __future__ import annotations

from alembic import op

revision = "0884"
down_revision = "0883"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION pii_reveal_whole_seconds() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            NEW.expires_at := NEW.revealed_at + make_interval(
                secs => round(extract(epoch FROM NEW.expires_at - NEW.revealed_at))
            );
            RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER pii_reveals_whole_seconds BEFORE INSERT ON pii_reveals "
        "FOR EACH ROW EXECUTE FUNCTION pii_reveal_whole_seconds()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER pii_reveals_whole_seconds ON pii_reveals")
    op.execute("DROP FUNCTION pii_reveal_whole_seconds()")
