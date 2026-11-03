"""ADR P-58 ledger path: a trial balance read from a document (A-05-T28; A-05 §4.2; EBP-06;
DEC-2208; expand-only).

A trust report's trial balance (EBP-06) is extracted from the trustee's PDF by code, every line
cited, and recorded as a ledger snapshot like any import. `ledger_snapshots` gains
`source_evidence_version_id` and `extraction_run_id`, and a snapshot whose source is
`document_extraction` must carry both (CHECK). The columns are set on insert only: snapshots stay
immutable (ADR-004; the existing triggers refuse every update). Adoption into the TB of record
stays A-02's human-only version.

Revision ID: 0659
Revises: 0658
"""

from __future__ import annotations

from alembic import op

revision = "0659"
down_revision = "0658"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE ledger_snapshots
            ADD COLUMN source_evidence_version_id uuid NULL,
            ADD COLUMN extraction_run_id uuid NULL,
            ADD CONSTRAINT ledger_snapshots_document_provenance CHECK (
                source <> 'document_extraction'
                OR (source_evidence_version_id IS NOT NULL AND extraction_run_id IS NOT NULL)
            )
        """
    )
    op.execute(
        "GRANT INSERT (source_evidence_version_id, extraction_run_id) ON ledger_snapshots "
        "TO abacus_app"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE ledger_snapshots DROP CONSTRAINT ledger_snapshots_document_provenance, "
        "DROP COLUMN source_evidence_version_id, DROP COLUMN extraction_run_id"
    )
