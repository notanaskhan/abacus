"""R-01-T08: where a shared comment came from (R-01 §3.3 Story 3.1; contract portal-pbc §2).

- `comments.origin` (`thread` by default, or `ignore_note`): a client's optional note on an Ignore
  is stored as a shared, sealed, insert-only comment on the request with origin `ignore_note`, so
  the firm reads it in BND-02 and the thread; an Undo of the Ignore never removes it. The app's
  insert grant gains the column.

Revision ID: 0157
Revises: 0156
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns

revision = "0157"
down_revision = "0156"
branch_labels = None
depends_on = None

_INSERT_V1 = (
    *("id", "tenant_id", "engagement_id", "request_item_id", "evidence_version_id"),
    *("author_user_id", "author_side", "visibility", "body_sealed", "body_fingerprint"),
    "corrects_comment_id",
)


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE comments
            ADD COLUMN origin text NOT NULL DEFAULT 'thread'
                CHECK (origin IN ('thread', 'ignore_note')),
            ADD CONSTRAINT comments_ignore_note_shared
                CHECK (origin <> 'ignore_note'
                       OR (visibility = 'shared' AND author_side = 'client'
                           AND evidence_version_id IS NULL AND corrects_comment_id IS NULL))
        """
    )
    insert_columns(op, "comments", (*_INSERT_V1, "origin"))


def downgrade() -> None:
    insert_columns(op, "comments", _INSERT_V1)
    op.execute(
        "ALTER TABLE comments DROP CONSTRAINT comments_ignore_note_shared, DROP COLUMN origin"
    )
