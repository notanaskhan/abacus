"""The engagement record's version and period label, the interim recorded letter (P-07-T15;
DEC-224) and ENG-03's engagement drafts (P-07-T16; P-07 §4.2 M2; DEC-225).

- `engagements.version` starts at 1 and a trigger adds one on every update that changes the row
  (as `clients.version`, 0110), so ENG-02's record carries a version a later edit can name. The
  app never writes the column.
- `engagements.period_label` (`PY2025`, `TY2025`, `Oct-Dec 2026`): a short label, 40 characters
  at most, set by the wizard (P-07-T16).
- `engagement_letters` gains the interim recorded letter's facts (G3 until C7): both parties'
  signature dates, the client signer (a contact) and the firm signer (a person), the signed copy
  (an evidence version stored write-once first) and the person who recorded it. Both dates on
  or after the G1 decision is the service's rule (409 `letter_before_acceptance`).
- New `engagement_drafts` (P-07-T16; P-07 §4.2 M2; DEC-225): ENG-03's autosaved wizard state, its
  owner's only (the service filters by `created_by`; RLS by tenant). The payload holds
  identifiers and typed values only (no TIN, no free text beyond the engagement name); `version`
  is the autosave's `seen_version`. A draft is discarded (`discarded_at`) or created
  (`created_engagement_id`), never deleted by the app; the purge 30 days later is operational.

Revision ID: 0124
Revises: 0123
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0124"
down_revision = "0123"
branch_labels = None
depends_on = None

_STEPS = (
    "'client_type', 'standards_methodology', 'period_deadlines', 'team_independence', "
    "'binder_portal', 'letter_review'"
)
_DRAFT_UPDATES = (
    "client_id",
    "client_entity_id",
    "type_code",
    "step",
    "payload",
    "prospect_engagement_id",
    "created_engagement_id",
    "version",
    "saved_at",
    "discarded_at",
)
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

    op.execute(
        f"""
        CREATE TABLE engagement_drafts (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            created_by uuid NOT NULL,
            client_id uuid NULL,
            client_entity_id uuid NULL,
            type_code text NULL CHECK (type_code ~ '^[a-z0-9_]{{1,40}}$'),
            step text NOT NULL DEFAULT 'client_type' CHECK (step IN ({_STEPS})),
            payload jsonb NOT NULL DEFAULT '{{}}'::jsonb
                CHECK (jsonb_typeof(payload) = 'object' AND octet_length(payload::text) <= 16384),
            prospect_engagement_id uuid NULL,
            created_engagement_id uuid NULL,
            version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
            saved_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            discarded_at timestamptz NULL,
            UNIQUE (tenant_id, id),
            CHECK (discarded_at IS NULL OR created_engagement_id IS NULL),
            FOREIGN KEY (tenant_id, client_id) REFERENCES clients (tenant_id, id),
            FOREIGN KEY (tenant_id, client_entity_id) REFERENCES client_entities (tenant_id, id),
            FOREIGN KEY (tenant_id, prospect_engagement_id) REFERENCES engagements (tenant_id, id),
            FOREIGN KEY (tenant_id, created_engagement_id) REFERENCES engagements (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX engagement_drafts_by_owner ON engagement_drafts "
        "(tenant_id, created_by, saved_at)"
    )
    tenant_table(op, "engagement_drafts")
    op.execute("REVOKE UPDATE, DELETE ON engagement_drafts FROM abacus_app")
    insert_columns(
        op,
        "engagement_drafts",
        (
            "tenant_id",
            "created_by",
            "client_id",
            "client_entity_id",
            "type_code",
            "step",
            "payload",
        ),
    )
    op.execute(f"GRANT UPDATE ({', '.join(_DRAFT_UPDATES)}) ON engagement_drafts TO abacus_app")


def downgrade() -> None:
    op.execute("DROP TABLE engagement_drafts")
    op.execute(
        "ALTER TABLE engagement_letters "
        + ", ".join(f"DROP COLUMN {column}" for column in _LETTER)
    )
    op.execute("ALTER TABLE engagements DROP COLUMN period_label")
    op.execute("DROP TRIGGER engagements_bump_version ON engagements")
    op.execute("DROP FUNCTION engagements_bump_version()")
    op.execute("ALTER TABLE engagements DROP COLUMN version")
