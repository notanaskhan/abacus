"""Review notes (SPEC-041; TASK-103).

- `review_notes` (insert-only): a reviewer's note on a fieldwork row (`selected_item_id`) or on
  the procedure's workpaper (null).
- `review_note_events` (insert-only): responses, reopenings and the clearing; the newest event is
  the note's state (none: Open).

Revision ID: 0062
Revises: 0061
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0062"
down_revision = "0061"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE review_notes (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            procedure_id uuid NOT NULL,
            selected_item_id uuid NULL,
            body text NOT NULL CHECK (length(body) BETWEEN 1 AND 2000),
            raised_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id),
            FOREIGN KEY (tenant_id, procedure_id) REFERENCES procedures (tenant_id, id),
            FOREIGN KEY (tenant_id, selected_item_id) REFERENCES selected_items (tenant_id, id)
        )
        """
    )
    op.execute("CREATE INDEX review_notes_by_procedure ON review_notes (tenant_id, procedure_id)")
    tenant_table(op, "review_notes")
    op.execute("REVOKE UPDATE, DELETE ON review_notes FROM abacus_app")
    insert_columns(
        op,
        "review_notes",
        ("tenant_id", "engagement_id", "procedure_id", "selected_item_id", "body", "raised_by"),
    )
    op.execute(
        """
        CREATE TABLE review_note_events (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            review_note_id uuid NOT NULL,
            kind text NOT NULL CHECK (kind IN ('responded', 'reopened', 'cleared')),
            body text NULL CHECK (length(body) BETWEEN 1 AND 2000),
            by_user uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            CHECK (kind = 'cleared' OR body IS NOT NULL),
            FOREIGN KEY (tenant_id, review_note_id) REFERENCES review_notes (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX review_note_events_by_note ON review_note_events (tenant_id, review_note_id)"
    )
    tenant_table(op, "review_note_events")
    op.execute("REVOKE UPDATE, DELETE ON review_note_events FROM abacus_app")
    insert_columns(
        op, "review_note_events", ("tenant_id", "review_note_id", "kind", "body", "by_user")
    )


def downgrade() -> None:
    op.execute("DROP TABLE review_note_events")
    op.execute("DROP TABLE review_notes")
