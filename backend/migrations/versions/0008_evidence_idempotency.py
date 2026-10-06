"""Evidence version idempotency key; protect evidence from downgrades (TASK-009 reviews).

A retried writer (a Temporal activity whose commit succeeded but whose acknowledgement was lost)
passes the same idempotency key and gets the existing version back, not a duplicate (ADR-018).

Downgrading past this revision would drop evidence: it refuses while any version exists.

Revision ID: 0008
Revises: 0007
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

_COLUMNS = (
    "id",
    "tenant_id",
    "engagement_id",
    "evidence_item_id",
    "version_no",
    "fingerprint",
    "storage_key",
    "storage_version_id",
    "size_bytes",
    "media_type",
    "source",
    "method",
    "pulled_at",
    "period_start",
    "period_end",
    "client_entity_id",
    "snapshot_id",
)


def upgrade() -> None:
    op.execute(
        "ALTER TABLE evidence_versions ADD COLUMN idempotency_key text NULL "
        "CHECK (length(idempotency_key) BETWEEN 1 AND 200)"
    )
    op.execute(
        "CREATE UNIQUE INDEX evidence_versions_idempotency ON evidence_versions "
        "(tenant_id, idempotency_key) WHERE idempotency_key IS NOT NULL"
    )
    insert_columns(op, "evidence_versions", (*_COLUMNS, "idempotency_key"))


def downgrade() -> None:
    op.execute(
        "DO $$ BEGIN "
        "IF EXISTS (SELECT 1 FROM evidence_versions) THEN "
        "RAISE EXCEPTION 'refusing to downgrade: evidence versions exist (ADR-004)'; "
        "END IF; END $$"
    )
    insert_columns(op, "evidence_versions", _COLUMNS)
    op.execute("DROP INDEX evidence_versions_idempotency")
    op.execute("ALTER TABLE evidence_versions DROP COLUMN idempotency_key")
