"""T-05-T42 (S41; TASK-7703; T-05 F7, F8; DEC-4705): workbook sections and self-check issues the
system resolves, expand-only.

- `tax_workbook_sections` (tax): one row per (return, section key) the first time a section is read
  or signed, so a section has a stable id for P-04's sign-offs (the `tax_workbook_section`
  reviewable). Insert-only: a section's content hash is computed from its cells, never stored.
  Every row carries its tenant, engagement and the return's work item; forced RLS through
  `tenant_table()`.
- `tax_section_acknowledgements` (tax, insert-only): a sign-off given while a tie-out is off
  carries the person's note, sealed under the firm's key and bound to the row (`note_sealed`),
  with its SHA-256 (the audit event names the hash only), and the sign-off it explains.
- `issues`: a `self_check` issue may also be `system_resolved_only` (a tie-out the run raised
  resolves when the tie passes, never by a person's resolve; 0800's trigger keeps that rule for
  any such issue). The constraint `issues_system_resolved_dependency` is widened to it.

The pipeline runs it after 8 pm CT inside the window (P-29).

Revision ID: 0860
Revises: 0851
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0860"
down_revision = "0851"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE tax_workbook_sections (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            work_item_id uuid NOT NULL,
            key text NOT NULL CHECK (key ~ '^[a-z][a-z0-9-]{0,39}$'),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (work_item_id, key),
            FOREIGN KEY (tenant_id, engagement_id, work_item_id)
                REFERENCES work_items (tenant_id, engagement_id, id),
            FOREIGN KEY (work_item_id) REFERENCES tax_returns (work_item_id) ON DELETE RESTRICT
        )
        """
    )
    op.execute(
        """
        CREATE TABLE tax_section_acknowledgements (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            work_item_id uuid NOT NULL,
            section_id uuid NOT NULL,
            sign_off_id uuid NOT NULL,
            off_count integer NOT NULL CHECK (off_count >= 1),
            note_sealed bytea NOT NULL CHECK (octet_length(note_sealed) BETWEEN 1 AND 8192),
            note_sha256 text NOT NULL CHECK (note_sha256 ~ '^[0-9a-f]{64}$'),
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (sign_off_id),
            FOREIGN KEY (tenant_id, section_id) REFERENCES tax_workbook_sections (tenant_id, id),
            FOREIGN KEY (tenant_id, engagement_id, work_item_id)
                REFERENCES work_items (tenant_id, engagement_id, id),
            FOREIGN KEY (tenant_id, created_by) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    tenant_table(op, "tax_workbook_sections")
    op.execute("REVOKE UPDATE, DELETE, TRUNCATE ON tax_workbook_sections FROM abacus_app")
    insert_columns(
        op, "tax_workbook_sections", ("tenant_id", "engagement_id", "work_item_id", "key")
    )
    insert_only(op, "tax_workbook_sections")
    tenant_table(op, "tax_section_acknowledgements")
    op.execute("REVOKE UPDATE, DELETE, TRUNCATE ON tax_section_acknowledgements FROM abacus_app")
    insert_columns(
        op,
        "tax_section_acknowledgements",
        (
            "tenant_id", "engagement_id", "work_item_id", "section_id", "sign_off_id",
            "off_count", "note_sealed", "note_sha256", "created_by",
        ),
    )  # fmt: skip
    insert_only(op, "tax_section_acknowledgements")
    op.execute("ALTER TABLE issues DROP CONSTRAINT issues_system_resolved_dependency")
    op.execute(
        "ALTER TABLE issues ADD CONSTRAINT issues_system_resolved_dependency "
        "CHECK (NOT system_resolved_only OR source_kind IN ('k1_dependency', 'self_check'))"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE issues DROP CONSTRAINT issues_system_resolved_dependency")
    op.execute(
        "ALTER TABLE issues ADD CONSTRAINT issues_system_resolved_dependency "
        "CHECK (NOT system_resolved_only OR source_kind = 'k1_dependency')"
    )
    op.execute("DROP TABLE tax_section_acknowledgements")
    op.execute("DROP TABLE tax_workbook_sections")
