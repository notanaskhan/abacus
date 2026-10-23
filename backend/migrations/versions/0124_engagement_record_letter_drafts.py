"""The engagement record's version and period label, and the interim recorded letter (P-07-T15;
P-07 §4.2 M2's `engagements.period_label`; DEC-224).

- `engagements.version` starts at 1 and a trigger adds one on every update that changes the row
  (as `clients.version`, 0110), so ENG-02's record carries a version a later edit can name. The
  app never writes the column.
- `engagements.period_label` (`PY2025`, `TY2025`, `Oct-Dec 2026`): a short label, 40 characters
  at most, set by the wizard (P-07-T16).
- `engagement_letters` gains the interim recorded letter's facts (G3 until C7): both parties'
  signature dates, the client signer (a contact) and the firm signer (a person), the signed copy
  (an evidence version stored write-once first) and the person who recorded it. Both dates on
  or after the G1 decision is the service's rule (409 `letter_before_acceptance`).

Revision ID: 0124
Revises: 0123
"""

from __future__ import annotations

from alembic import op

revision = "0124"
down_revision = "0123"
branch_labels = None
depends_on = None

_LETTER = (
    "client_signed_on",
    "firm_signed_on",
    "client_signer_contact_id",
    "firm_signer_user_id",
    "signed_copy_version_id",
    "recorded_by_user_id",
)


def upgrade() -> None:
    op.execute(
        "ALTER TABLE engagements ADD COLUMN version integer NOT NULL DEFAULT 1 "
        "CHECK (version >= 1)"
    )
    op.execute(
        """
        CREATE FUNCTION engagements_bump_version() RETURNS trigger
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
        "CREATE TRIGGER engagements_bump_version BEFORE UPDATE ON engagements "
        "FOR EACH ROW EXECUTE FUNCTION engagements_bump_version()"
    )
    op.execute(
        "ALTER TABLE engagements ADD COLUMN period_label text NULL "
        "CHECK (char_length(period_label) BETWEEN 1 AND 40)"
    )
    op.execute("GRANT UPDATE (period_label) ON engagements TO abacus_app")

    op.execute(
        """
        ALTER TABLE engagement_letters
            ADD COLUMN client_signed_on date NULL,
            ADD COLUMN firm_signed_on date NULL,
            ADD COLUMN client_signer_contact_id uuid NULL,
            ADD COLUMN firm_signer_user_id uuid NULL,
            ADD COLUMN signed_copy_version_id uuid NULL,
            ADD COLUMN recorded_by_user_id uuid NULL
        """
    )
    op.execute(f"GRANT UPDATE ({', '.join(_LETTER)}) ON engagement_letters TO abacus_app")


def downgrade() -> None:
    op.execute(
        "ALTER TABLE engagement_letters "
        + ", ".join(f"DROP COLUMN {column}" for column in _LETTER)
    )
    op.execute("ALTER TABLE engagements DROP COLUMN period_label")
    op.execute("DROP TRIGGER engagements_bump_version ON engagements")
    op.execute("DROP FUNCTION engagements_bump_version()")
    op.execute("ALTER TABLE engagements DROP COLUMN version")
