"""The composed engagement letter's versions (N-02-T32; N-02 §4.2
`00NN_engagement_letter_versions`; ENG-04; DEC-1458). Expand-only.

- `engagement_letter_versions`: one row per composed version of an engagement's letter (an
  original or an addendum that amends one). The content (template version, clause states,
  variables, section overrides, fee terms, the generated document) is fixed at insert: an edit
  is a new version, and the version it replaces moves to `superseded`. Only the lifecycle columns
  change after insert (status, the approval and the envelope), forward only, and a trigger
  refuses any other change and every delete (ADR-004). A partner-approved row carries who
  approved, when, and the content hash they approved (INV-1's database layer; N-02-T33 adds the
  partner and fresh-MFA checks above it).
- `engagement_letters` gains `current_version_id`, `mode` (`composed` or `recorded`; every
  existing row is a recorded letter) and `envelope_id`. The record-mode columns stay.

No data is inserted: letter templates and the clause library are database content imported
through P-11 (KNW-03), never a migration.

Revision ID: 0560
Revises: 0550, 0431 (joins main's two heads: T-01-T43's 0550 and N-01-T22's 0431)
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0560"
down_revision = ("0550", "0431")
branch_labels = None
depends_on = None

VERSION_INSERT = (
    "id",
    "tenant_id",
    "engagement_id",
    "version_no",
    "kind",
    "amends_version_id",
    "template_version_id",
    "clause_states",
    "variables",
    "section_overrides",
    "fee_terms",
    "generated_document_id",
    "content_hash",
    "status",
    "created_by",
    "created_by_kind",
)
VERSION_UPDATE = ("status", "approved_by", "approved_at", "approval_content_hash", "envelope_id")


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE engagement_letter_versions (
            id uuid NOT NULL,
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            version_no integer NOT NULL CHECK (version_no >= 1),
            kind text NOT NULL CHECK (kind IN ('original', 'addendum')),
            amends_version_id uuid NULL,
            template_version_id uuid NOT NULL,
            clause_states jsonb NOT NULL DEFAULT '{}'::jsonb
                CHECK (jsonb_typeof(clause_states) = 'object'),
            variables jsonb NOT NULL DEFAULT '{}'::jsonb
                CHECK (jsonb_typeof(variables) = 'object'),
            section_overrides jsonb NOT NULL DEFAULT '{}'::jsonb
                CHECK (jsonb_typeof(section_overrides) = 'object'),
            fee_terms jsonb NOT NULL DEFAULT '{}'::jsonb
                CHECK (jsonb_typeof(fee_terms) = 'object'),
            generated_document_id uuid NOT NULL,
            content_hash text NOT NULL CHECK (content_hash ~ '^[0-9a-f]{64}$'),
            status text NOT NULL DEFAULT 'draft' CHECK (
                status IN ('draft', 'partner_approved', 'sent', 'signed', 'superseded')
            ),
            approved_by uuid NULL,
            approved_at timestamptz NULL,
            approval_content_hash text NULL CHECK (approval_content_hash ~ '^[0-9a-f]{64}$'),
            envelope_id uuid NULL,
            created_by uuid NOT NULL,
            created_by_kind text NOT NULL CHECK (created_by_kind IN ('human', 'agent')),
            created_at timestamptz NOT NULL DEFAULT abacus_now(),
            PRIMARY KEY (tenant_id, id),
            UNIQUE (tenant_id, engagement_id, version_no),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id),
            FOREIGN KEY (tenant_id, amends_version_id)
                REFERENCES engagement_letter_versions (tenant_id, id),
            FOREIGN KEY (tenant_id, generated_document_id)
                REFERENCES generated_documents (tenant_id, id),
            CHECK ((kind = 'addendum') = (amends_version_id IS NOT NULL)),
            -- INV-1's database layer: an approval names its person, time and hash, together.
            CHECK (
                (approved_by IS NULL) = (approved_at IS NULL)
                AND (approved_by IS NULL) = (approval_content_hash IS NULL)
            ),
            CHECK (status <> 'partner_approved' OR approved_by IS NOT NULL),
            CHECK (status NOT IN ('sent', 'signed') OR envelope_id IS NOT NULL)
        )
        """
    )
    op.execute(
        "CREATE INDEX engagement_letter_versions_latest ON engagement_letter_versions "
        "(tenant_id, engagement_id, version_no DESC)"
    )
    op.execute(
        """
        CREATE FUNCTION engagement_letter_versions_guard() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            IF TG_OP <> 'UPDATE' THEN
                RAISE EXCEPTION 'engagement_letter_versions is insert-only'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF (NEW.tenant_id, NEW.engagement_id, NEW.version_no, NEW.kind,
                NEW.amends_version_id, NEW.template_version_id, NEW.clause_states,
                NEW.variables, NEW.section_overrides, NEW.fee_terms,
                NEW.generated_document_id, NEW.content_hash, NEW.created_by,
                NEW.created_by_kind, NEW.created_at)
               IS DISTINCT FROM
               (OLD.tenant_id, OLD.engagement_id, OLD.version_no, OLD.kind,
                OLD.amends_version_id, OLD.template_version_id, OLD.clause_states,
                OLD.variables, OLD.section_overrides, OLD.fee_terms,
                OLD.generated_document_id, OLD.content_hash, OLD.created_by,
                OLD.created_by_kind, OLD.created_at) THEN
                RAISE EXCEPTION 'a letter version''s content never changes'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF OLD.approved_by IS NOT NULL AND (NEW.approved_by, NEW.approved_at,
                NEW.approval_content_hash) IS DISTINCT FROM (OLD.approved_by, OLD.approved_at,
                OLD.approval_content_hash) THEN
                RAISE EXCEPTION 'an approval is never rewritten'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF NEW.status IS DISTINCT FROM OLD.status AND NOT (
                (OLD.status = 'draft' AND NEW.status IN ('partner_approved', 'superseded'))
                OR (OLD.status = 'partner_approved' AND NEW.status IN ('sent', 'superseded'))
                OR (OLD.status = 'sent' AND NEW.status IN ('signed', 'superseded'))
            ) THEN
                RAISE EXCEPTION 'letter version % cannot move from % to %',
                    OLD.id, OLD.status, NEW.status USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER engagement_letter_versions_guard BEFORE UPDATE OR DELETE "
        "ON engagement_letter_versions FOR EACH ROW "
        "EXECUTE FUNCTION engagement_letter_versions_guard()"
    )
    op.execute(
        "CREATE TRIGGER engagement_letter_versions_no_truncate BEFORE TRUNCATE "
        "ON engagement_letter_versions FOR EACH STATEMENT "
        "EXECUTE FUNCTION engagement_letter_versions_guard()"
    )
    tenant_table(op, "engagement_letter_versions")
    op.execute("REVOKE UPDATE, DELETE, TRUNCATE ON engagement_letter_versions FROM abacus_app")
    insert_columns(op, "engagement_letter_versions", VERSION_INSERT)
    op.execute(
        f"GRANT UPDATE ({', '.join(VERSION_UPDATE)}) ON engagement_letter_versions TO abacus_app"
    )

    op.execute(
        """
        ALTER TABLE engagement_letters
            ADD COLUMN current_version_id uuid NULL,
            ADD COLUMN mode text NOT NULL DEFAULT 'recorded'
                CHECK (mode IN ('composed', 'recorded')),
            ADD COLUMN envelope_id uuid NULL,
            ADD CONSTRAINT engagement_letters_current_version
                FOREIGN KEY (tenant_id, current_version_id)
                REFERENCES engagement_letter_versions (tenant_id, id),
            ADD CONSTRAINT engagement_letters_composed_has_version
                CHECK (mode = 'recorded' OR current_version_id IS NOT NULL)
        """
    )
    op.execute(
        "GRANT UPDATE (current_version_id, mode, envelope_id) ON engagement_letters TO abacus_app"
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE engagement_letters
            DROP CONSTRAINT engagement_letters_composed_has_version,
            DROP CONSTRAINT engagement_letters_current_version,
            DROP COLUMN envelope_id,
            DROP COLUMN mode,
            DROP COLUMN current_version_id
        """
    )
    op.execute("DROP TABLE engagement_letter_versions")
    op.execute("DROP FUNCTION engagement_letter_versions_guard()")
