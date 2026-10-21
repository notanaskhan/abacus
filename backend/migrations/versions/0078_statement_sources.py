"""Where approved statement values were printed (TASK-334).

- `statement_transactions.box`: the line's box on its page (x0, top, x1, bottom as fractions of
  the page), so a transaction points back to the line it came from.
- `statement_datasets.field_sources`: the page and box of each printed summary value (opening,
  closing, period, last 4).
Both nullable: CSV and OFX lines, and older extractions, have no boxes. Still insert-only.

Revision ID: 0078
Revises: 0077
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns

revision = "0078"
down_revision = "0077"
branch_labels = None
depends_on = None

_TRANSACTION_COLUMNS = (
    "tenant_id",
    "dataset_id",
    "position",
    "posted_on",
    "description",
    "amount",
    "page",
    "excluded",
    "exclusion_reason",
)
_DATASET_COLUMNS = (
    "tenant_id",
    "engagement_id",
    "request_item_id",
    "evidence_version_id",
    "format",
    "account_kind",
    "issuer",
    "last4",
    "period_start",
    "period_end",
    "opening",
    "closing",
    "opening_source",
    "closing_source",
    "included_total",
    "line_count",
    "excluded_count",
    "signs_flipped",
    "approved_by",
    "actor_kind",
)


def upgrade() -> None:
    op.execute(
        "ALTER TABLE statement_transactions ADD COLUMN box real[] NULL "
        "CHECK (box IS NULL OR cardinality(box) = 4)"
    )
    op.execute("ALTER TABLE statement_datasets ADD COLUMN field_sources jsonb NULL")
    insert_columns(op, "statement_transactions", (*_TRANSACTION_COLUMNS, "box"))
    insert_columns(op, "statement_datasets", (*_DATASET_COLUMNS, "field_sources"))


def downgrade() -> None:
    insert_columns(op, "statement_transactions", _TRANSACTION_COLUMNS)
    insert_columns(op, "statement_datasets", _DATASET_COLUMNS)
    op.execute("ALTER TABLE statement_transactions DROP COLUMN box")
    op.execute("ALTER TABLE statement_datasets DROP COLUMN field_sources")
