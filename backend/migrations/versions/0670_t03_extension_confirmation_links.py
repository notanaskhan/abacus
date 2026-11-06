"""T-03-T07 (DEC-2350): the confirmation links TAX-13 reads, expand-only.

`filing_extensions.confirmation_request_item_id` holds the extension's confirmation request (POR-10
and TAX-13 read one request item, never a task), as `estimate_installments` already did.
`estimate_installments.paid_evidence_version_id` is the evidence a Paid cell opens in SHL-08
(T-03 US-5.3). Both nullable with no default, so no table rewrite.

Revision ID: 0670
Revises: 0669
"""

from __future__ import annotations

from alembic import op

revision = "0670"
down_revision = "0669"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE filing_extensions ADD COLUMN confirmation_request_item_id uuid NULL")
    op.execute("ALTER TABLE estimate_installments ADD COLUMN paid_evidence_version_id uuid NULL")
    op.execute("GRANT UPDATE (confirmation_request_item_id) ON filing_extensions TO abacus_app")
    op.execute("GRANT UPDATE (paid_evidence_version_id) ON estimate_installments TO abacus_app")


def downgrade() -> None:
    op.execute("ALTER TABLE estimate_installments DROP COLUMN paid_evidence_version_id")
    op.execute("ALTER TABLE filing_extensions DROP COLUMN confirmation_request_item_id")
