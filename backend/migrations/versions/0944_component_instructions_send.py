"""Component instructions: the firm's letter template family and the send with Undo (A-09-T27;
A-09 §3.6 Story 6.1; SPEC-658 F6; AUD-35 a, b; DEC-5405).

- `report_templates.family` and `generated_documents.kind` gain `component_instructions`: the
  firm's instructions letter is DB content (C11), merged by code and rendered through C11.
- `component_instruction_sends`: a person's send of one version to one recipient. It completes
  10 seconds later (the grant, the invitation, `component_instructions.sent`) unless the sender
  undoes it first; nothing is sent while it is pending. Insert-only but the one completion or
  undo stamp.

Revision ID: 0944
Revises: 0943
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0944"
down_revision = "0943"
branch_labels = None
depends_on = None

_OLD = (
    "engagement_letter",
    "consent_7216",
    "representation_letter",
    "governance_letter",
    "audit_report",
    "review_report",
    "compilation_report",
    "notice_response",
    "delivery_cover_letter",
    "k1_cover_letter",
    "fs_package",
    "run_trace_export",
    "ebp_supplemental_schedule",
    "client_entries_journal",
)
_NEW = (*_OLD, "component_instructions")
_CHECKS = (
    ("generated_documents", "generated_documents_kind_check", "kind"),
    ("report_templates", "report_templates_family_check", "family"),
)
INSERTS = (
    "tenant_id", "engagement_id", "work_item_id", "instructions_id", "version_id",
    "recipient_contact_id", "sent_by", "content_hash", "generated_document_id",
)  # fmt: skip
UPDATES = ("completed_at", "undone_at", "grant_id")


def _in(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


def upgrade() -> None:
    for table, check, column in _CHECKS:
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {check}")
        op.execute(f"ALTER TABLE {table} ADD CONSTRAINT {check} CHECK ({column} IN ({_in(_NEW)}))")
    op.execute(
        """
        CREATE TABLE component_instruction_sends (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            work_item_id uuid NOT NULL,
            instructions_id uuid NOT NULL,
            version_id uuid NOT NULL,
            recipient_contact_id uuid NOT NULL,
            sent_by uuid NOT NULL,
            content_hash text NOT NULL CHECK (content_hash ~ '^[0-9a-f]{64}$'),
            generated_document_id uuid NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            completed_at timestamptz NULL,
            undone_at timestamptz NULL,
            grant_id uuid NULL,
            UNIQUE (tenant_id, id),
            -- A send ends once: completed or undone, never both.
            CHECK (completed_at IS NULL OR undone_at IS NULL),
            CHECK (undone_at IS NULL OR undone_at <= created_at + interval '10 seconds'),
            FOREIGN KEY (tenant_id, instructions_id)
                REFERENCES component_instructions (tenant_id, id),
            FOREIGN KEY (tenant_id, version_id)
                REFERENCES component_instruction_versions (tenant_id, id),
            FOREIGN KEY (tenant_id, recipient_contact_id) REFERENCES contacts (tenant_id, id),
            FOREIGN KEY (tenant_id, sent_by) REFERENCES memberships (tenant_id, user_id),
            FOREIGN KEY (tenant_id, engagement_id, work_item_id)
                REFERENCES work_items (tenant_id, engagement_id, id)
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX component_instruction_sends_one_open ON component_instruction_sends "
        "(tenant_id, instructions_id) WHERE completed_at IS NULL AND undone_at IS NULL"
    )
    tenant_table(op, "component_instruction_sends")
    insert_columns(op, "component_instruction_sends", INSERTS)
    op.execute("REVOKE UPDATE, DELETE ON component_instruction_sends FROM abacus_app")
    op.execute(f"GRANT UPDATE ({', '.join(UPDATES)}) ON component_instruction_sends TO abacus_app")


def downgrade() -> None:
    op.execute("DROP TABLE component_instruction_sends")
    op.execute("DELETE FROM generated_documents WHERE kind = 'component_instructions'")
    op.execute("DELETE FROM report_templates WHERE family = 'component_instructions'")
    for table, check, column in _CHECKS:
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {check}")
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {check} "
            f"CHECK ({column} IN ({_in(_OLD)})) NOT VALID"
        )
