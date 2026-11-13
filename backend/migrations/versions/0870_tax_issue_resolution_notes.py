"""T-05-T51 (S42; TASK-7902; T-05 F8; TXP-10; DEC-4904): the note a person gives when resolving an
entity return's issue that no approved fix closed, expand-only.

- `tax_issue_resolution_notes` (tax, insert-only): one row per note, sealed under the firm's key
  and bound to the row (`note_sealed`), with its SHA-256 (the audit event names the hash only),
  the issue it explains and the person who wrote it. Every row carries its tenant, engagement and
  the return's work item; forced RLS through `tenant_table()`. The issue itself stays P-04's
  (C3); `issue_id` is a reference, not a foreign key into review's table.

The pipeline runs it after 8 pm CT inside the window (P-29).

Revision ID: 0870
Revises: 0860
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0870"
down_revision = "0860"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE tax_issue_resolution_notes (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            work_item_id uuid NOT NULL,
            issue_id uuid NOT NULL,
            note_sealed bytea NOT NULL CHECK (octet_length(note_sealed) BETWEEN 1 AND 8192),
            note_sha256 text NOT NULL CHECK (note_sha256 ~ '^[0-9a-f]{64}$'),
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, engagement_id, work_item_id)
                REFERENCES work_items (tenant_id, engagement_id, id),
            FOREIGN KEY (work_item_id) REFERENCES tax_returns (work_item_id) ON DELETE RESTRICT,
            FOREIGN KEY (tenant_id, created_by) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX tax_issue_resolution_notes_issue ON tax_issue_resolution_notes (issue_id)"
    )
    tenant_table(op, "tax_issue_resolution_notes")
    op.execute("REVOKE UPDATE, DELETE, TRUNCATE ON tax_issue_resolution_notes FROM abacus_app")
    insert_columns(
        op,
        "tax_issue_resolution_notes",
        (
            "tenant_id", "engagement_id", "work_item_id", "issue_id", "note_sealed",
            "note_sha256", "created_by",
        ),
    )  # fmt: skip
    insert_only(op, "tax_issue_resolution_notes")


def downgrade() -> None:
    op.execute("DROP TABLE tax_issue_resolution_notes")
