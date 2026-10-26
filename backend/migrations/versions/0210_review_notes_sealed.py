"""Sealed review note bodies (P-04-T21; ADR-160 clause 6; TASK-1400).

`reviewable_notes.body_sealed` arrived with 0093 but every note still stored its body in the
clear. From here a note and each of its events hold their text sealed (envelope encryption, bound
to the row), and the plaintext columns stay only for the SPEC-313 rows written before:

- `reviewable_notes.body` becomes nullable; a note holds exactly one of `body` and
  `body_sealed`.
- `reviewable_note_events` gains `body_sealed`. An event holds at most one form, and only a
  raise, a response or a reopen needs a body (a clear, a close or a withdrawal may carry none;
  0076 asked one of every event but a clear).
- The app may insert `id` on both, so the seal can be bound to its own row before the insert.

Revision ID: 0210
Revises: 0197
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns

revision = "0210"
down_revision = "0197"
branch_labels = None
depends_on = None

_NOTE_COLUMNS = (
    "tenant_id",
    "engagement_id",
    "target_type",
    "target_id",
    "anchor",
    "body",
    "raised_by",
    "assignee_user_id",
    "anchor_ref",
    "body_sealed",
)
_EVENT_COLUMNS = ("tenant_id", "note_id", "kind", "body", "by_user")


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE reviewable_notes
            ALTER COLUMN body DROP NOT NULL,
            ADD CONSTRAINT reviewable_notes_one_body
                CHECK (num_nonnulls(body, body_sealed) = 1)
        """
    )
    insert_columns(op, "reviewable_notes", ("id", *_NOTE_COLUMNS))
    op.execute(
        """
        ALTER TABLE reviewable_note_events
            DROP CONSTRAINT reviewable_note_events_check,
            ADD COLUMN body_sealed bytea NULL CHECK (octet_length(body_sealed) <= 65536),
            ADD CONSTRAINT reviewable_note_events_one_body
                CHECK (num_nonnulls(body, body_sealed) <= 1),
            ADD CONSTRAINT reviewable_note_events_body_when_needed
                CHECK (kind IN ('cleared', 'closed', 'withdrawn')
                    OR num_nonnulls(body, body_sealed) = 1)
        """
    )
    insert_columns(op, "reviewable_note_events", ("id", *_EVENT_COLUMNS, "body_sealed"))


def downgrade() -> None:
    # Sealed rows can't go back to a NOT NULL plaintext column: the downgrade refuses while any
    # exists (revert the code instead, which reads both forms).
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM reviewable_notes WHERE body_sealed IS NOT NULL)
               OR EXISTS (SELECT 1 FROM reviewable_note_events WHERE body_sealed IS NOT NULL)
               OR EXISTS (SELECT 1 FROM reviewable_note_events
                          WHERE kind <> 'cleared' AND body IS NULL) THEN
                RAISE EXCEPTION 'sealed review notes exist: 0210 cannot be downgraded';
            END IF;
        END $$
        """
    )
    insert_columns(op, "reviewable_note_events", _EVENT_COLUMNS)
    op.execute(
        """
        ALTER TABLE reviewable_note_events
            DROP CONSTRAINT reviewable_note_events_body_when_needed,
            DROP CONSTRAINT reviewable_note_events_one_body,
            DROP COLUMN body_sealed,
            ADD CONSTRAINT reviewable_note_events_check
                CHECK (kind = 'cleared' OR body IS NOT NULL)
        """
    )
    insert_columns(op, "reviewable_notes", _NOTE_COLUMNS)
    op.execute(
        """
        ALTER TABLE reviewable_notes
            DROP CONSTRAINT reviewable_notes_one_body,
            ALTER COLUMN body SET NOT NULL
        """
    )
