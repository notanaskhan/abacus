"""Review notes on any registered reviewable (SPEC-313; TASK-325; P-04).

- `reviewable_notes` (insert-only): a reviewer's note on a working paper or a trial balance,
  optionally anchored to a cell ("B4") or an account code. Fieldwork's procedure notes
  (`review_notes`, SPEC-041) move onto these later (DEC-110).
- `reviewable_note_events` (insert-only): responses, clearing and reopening; a note's state is
  its newest event's.

Revision ID: 0076
Revises: 0075
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0076"
down_revision = "0075"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE reviewable_notes (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            target_type text NOT NULL CHECK (target_type ~ '^[a-z][a-z_]{0,39}$'),
            target_id uuid NOT NULL,
            anchor text NULL CHECK (length(anchor) BETWEEN 1 AND 64),
            body text NOT NULL CHECK (length(body) BETWEEN 1 AND 2000),
            raised_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX reviewable_notes_by_target "
        "ON reviewable_notes (tenant_id, engagement_id, target_type, target_id)"
    )
    tenant_table(op, "reviewable_notes")
    op.execute("REVOKE UPDATE, DELETE ON reviewable_notes FROM abacus_app")
    insert_columns(
        op,
        "reviewable_notes",
        ("tenant_id", "engagement_id", "target_type", "target_id", "anchor", "body", "raised_by"),
    )
    op.execute(
        """
        CREATE TABLE reviewable_note_events (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            note_id uuid NOT NULL,
            kind text NOT NULL CHECK (kind IN ('responded', 'cleared', 'reopened')),
            body text NULL CHECK (length(body) BETWEEN 1 AND 2000),
            by_user uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            CHECK (kind = 'cleared' OR body IS NOT NULL),
            FOREIGN KEY (tenant_id, note_id) REFERENCES reviewable_notes (tenant_id, id)
        )
        """
    )
    tenant_table(op, "reviewable_note_events")
    op.execute("REVOKE UPDATE, DELETE ON reviewable_note_events FROM abacus_app")
    insert_columns(
        op, "reviewable_note_events", ("tenant_id", "note_id", "kind", "body", "by_user")
    )


def downgrade() -> None:
    op.execute("DROP TABLE reviewable_note_events")
    op.execute("DROP TABLE reviewable_notes")
