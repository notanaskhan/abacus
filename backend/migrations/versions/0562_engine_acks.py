"""The engine's e-file acknowledgements (T-01-T26; T-01 §3.10; tax-engine-bridge §6; DEC-1464).
Expand-only.

`engine_acks` (insert-only): one row per jurisdiction of an e-file status report a person
uploaded, kept `pending` for the e-file record (T-02) to take up. Only the submission id's last
four is stored (R-04: Accrued never transmits and keeps no transmission identifiers). The
rejection text is the engine's (client-system content, ADR-052). Tax's table, forced RLS.

Revision ID: 0562
Revises: 0561
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0562"
down_revision = "0561"
branch_labels = None
depends_on = None

ACK_INSERT = (
    "tenant_id",
    "return_id",
    "sync_event_id",
    "jurisdiction",
    "submission_last4",
    "status",
    "status_at",
    "reject_code",
    "reject_text",
)


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE engine_acks (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            return_id uuid NOT NULL,
            sync_event_id uuid NOT NULL,
            jurisdiction text NOT NULL CHECK (jurisdiction ~ '^(federal|[A-Z]{2})$'),
            submission_last4 text NOT NULL CHECK (submission_last4 ~ '^[A-Za-z0-9]{4}$'),
            status text NOT NULL CHECK (status IN ('accepted', 'rejected')),
            status_at text NOT NULL CHECK (length(status_at) BETWEEN 10 AND 32),
            reject_code text NULL CHECK (length(reject_code) BETWEEN 1 AND 40),
            reject_text text NULL CHECK (length(reject_text) <= 2000),
            state text NOT NULL DEFAULT 'pending' CHECK (state IN ('pending')),
            received_at timestamptz NOT NULL DEFAULT abacus_now(),
            UNIQUE (tenant_id, id),
            FOREIGN KEY (return_id) REFERENCES tax_returns (work_item_id),
            FOREIGN KEY (tenant_id, sync_event_id) REFERENCES engine_sync_events (tenant_id, id),
            CHECK (status <> 'rejected' OR reject_code IS NOT NULL)
        )
        """
    )
    op.execute(
        "CREATE INDEX engine_acks_return ON engine_acks (tenant_id, return_id, received_at)"
    )
    tenant_table(op, "engine_acks")
    op.execute("REVOKE TRUNCATE ON engine_acks FROM abacus_app")
    insert_only(op, "engine_acks")
    insert_columns(op, "engine_acks", ACK_INSERT)


def downgrade() -> None:
    op.execute("DROP TABLE engine_acks")
