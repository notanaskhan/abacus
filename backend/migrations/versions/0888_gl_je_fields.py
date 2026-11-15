"""A-08-T09 (S45; TASK-8048; ADR-400 proposed, P-58; SPEC-657 AC-0.7; red): GL journal-entry
fields, expand-only.

- `gl_entries` gains `posted_by` (the user who entered the entry; confidential), `entered_at`
  (when it was entered, not its posting date), `source` (`manual` or `system`) and `approver`, all
  nullable: an export fills them where it carries them (`connections/gl_formats.py`).
- `gl_snapshots` gains `je_fields_available text[]`, the subset of the four names the file's
  header carried, set at import; every existing snapshot reads `'{}'` (unavailable).

`ADD COLUMN` with a NULL or constant default rewrites no row and fires no row trigger, so no
immutable ledger row is updated (ADR-004); the insert-only triggers stand. The app may insert the
new columns and nothing else changes.

Revision ID: 0888
Revises: 0887
"""

from __future__ import annotations

from alembic import op

revision = "0888"
down_revision = "0887"
branch_labels = None
depends_on = None

_FIELDS = "'posted_by', 'entered_at', 'source', 'approver'"


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE gl_entries
            ADD COLUMN posted_by text NULL
                CONSTRAINT gl_entries_posted_by CHECK (length(posted_by) BETWEEN 1 AND 120),
            ADD COLUMN entered_at timestamptz NULL,
            ADD COLUMN source text NULL
                CONSTRAINT gl_entries_source CHECK (source IN ('manual', 'system')),
            ADD COLUMN approver text NULL
                CONSTRAINT gl_entries_approver CHECK (length(approver) BETWEEN 1 AND 120)
        """
    )
    op.execute(
        "GRANT INSERT (posted_by, entered_at, source, approver) ON gl_entries TO abacus_app"
    )
    op.execute(
        f"""
        ALTER TABLE gl_snapshots
            ADD COLUMN je_fields_available text[] NOT NULL DEFAULT '{{}}'
                CONSTRAINT gl_snapshots_je_fields
                CHECK (je_fields_available <@ ARRAY[{_FIELDS}]::text[])
        """
    )
    op.execute("GRANT INSERT (je_fields_available) ON gl_snapshots TO abacus_app")


def downgrade() -> None:
    op.execute("ALTER TABLE gl_snapshots DROP COLUMN je_fields_available")
    op.execute(
        "ALTER TABLE gl_entries DROP COLUMN approver, DROP COLUMN source, "
        "DROP COLUMN entered_at, DROP COLUMN posted_by"
    )
