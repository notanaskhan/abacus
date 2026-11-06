"""T-03-T07: an extension's confirmation request and its submission for approval.

`filing_extensions` gains `confirmation_request_item_id` (TAX-13 a's confirmation cell reads the
request item, never a task) and `submitted_by` and `submitted_at` (a preparer's Submit for
approval: C13's gate is open while a submitted extension has an unapproved payment). Expand only.
"""

from __future__ import annotations

from alembic import op

revision = "0670"
down_revision = "0669"
branch_labels = None
depends_on = None

_COLUMNS = ("confirmation_request_item_id", "submitted_by", "submitted_at")


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE filing_extensions
            ADD COLUMN confirmation_request_item_id uuid NULL,
            ADD COLUMN submitted_by uuid NULL,
            ADD COLUMN submitted_at timestamptz NULL,
            ADD CONSTRAINT filing_extensions_submitted
                CHECK ((submitted_by IS NULL) = (submitted_at IS NULL)),
            ADD FOREIGN KEY (tenant_id, confirmation_request_item_id)
                REFERENCES request_items (tenant_id, id)
        """
    )
    op.execute(f"GRANT UPDATE ({', '.join(_COLUMNS)}) ON filing_extensions TO abacus_app")


def downgrade() -> None:
    op.execute(f"REVOKE UPDATE ({', '.join(_COLUMNS)}) ON filing_extensions FROM abacus_app")
    op.execute(
        "ALTER TABLE filing_extensions DROP CONSTRAINT filing_extensions_submitted, "
        + ", ".join(f"DROP COLUMN {c}" for c in _COLUMNS)
    )
