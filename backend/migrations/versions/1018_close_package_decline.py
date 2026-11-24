"""C-02-T41 (S53; TASK-8925; C-02 F7 US-7.4; POR-08 c; R-02 C18; DEC-5927; amber): the client
can decline a released close package. Expand-only on `close_deliverables`:

- `status` admits `declined_by_client` (POR-08 c: "Declined · A number looks wrong"); the firm
  revises and releases again.
- Who declined, when, the reason code (C18's three: `number_looks_wrong`, `something_missing`,
  `other`) and the note sealed under the tenant's key (client text, ADR-052): written once by
  the `fs_package` provider's decide, inside C18's unit of work.

Revision ID: 1018
Revises: 1017
"""

from __future__ import annotations

from alembic import op

revision = "1018"
down_revision = "1017"
branch_labels = None
depends_on = None

_BEFORE = "('drafting', 'draft', 'released', 'approved_by_client')"
_AFTER = "('drafting', 'draft', 'released', 'approved_by_client', 'declined_by_client')"
_COLUMNS = (
    "client_declined_by_contact_id",
    "client_declined_at",
    "client_decline_reason",
    "client_decline_note_sealed",
)


def _status(kinds: str) -> None:
    op.execute("ALTER TABLE close_deliverables DROP CONSTRAINT close_deliverables_status_check")
    op.execute(
        "ALTER TABLE close_deliverables ADD CONSTRAINT close_deliverables_status_check "
        f"CHECK (status IN {kinds})"
    )


def upgrade() -> None:
    _status(_AFTER)
    op.execute(
        """
        ALTER TABLE close_deliverables
            ADD COLUMN client_declined_by_contact_id uuid NULL,
            ADD COLUMN client_declined_at timestamptz NULL,
            ADD COLUMN client_decline_reason text NULL
                CONSTRAINT close_deliverables_decline_reason CHECK (client_decline_reason IN
                    ('number_looks_wrong', 'something_missing', 'other')),
            ADD COLUMN client_decline_note_sealed bytea NULL,
            ADD CONSTRAINT close_deliverables_declined
                CHECK ((client_declined_at IS NULL) = (client_declined_by_contact_id IS NULL))
        """
    )
    op.execute(f"GRANT UPDATE ({', '.join(_COLUMNS)}) ON close_deliverables TO abacus_app")


def downgrade() -> None:
    op.execute(f"REVOKE UPDATE ({', '.join(_COLUMNS)}) ON close_deliverables FROM abacus_app")
    op.execute(
        "UPDATE close_deliverables SET status = 'released' WHERE status = 'declined_by_client'"
    )
    op.execute(
        "ALTER TABLE close_deliverables DROP CONSTRAINT close_deliverables_declined, "
        + ", ".join(f"DROP COLUMN {c}" for c in _COLUMNS)
    )
    _status(_BEFORE)
