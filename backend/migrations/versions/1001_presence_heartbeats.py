"""F-08-T13 (S52; TASK-8845; F-08 §F1; ADR P-15; chapter 03 §7.1; amber): `presence_heartbeats`,
who is on which object and where (a cell, section, card or the record), for 45 seconds. UNLOGGED
and forced RLS: presence is ephemeral by design, written through `kernel.ephemeral` (the documented
exception: not audited, never through the outbox), one row per person and object, replaced by each
heartbeat. Expand-only.

Revision ID: 1001
Revises: 1000
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import tenant_table

revision = "1001"
down_revision = "1000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE UNLOGGED TABLE presence_heartbeats (
            tenant_id uuid NOT NULL,
            user_id uuid NOT NULL,
            object_kind text NOT NULL CHECK (object_kind ~ '^[a-z][a-z_]{0,39}$'),
            object_id uuid NOT NULL,
            anchor_kind text NOT NULL CHECK (anchor_kind IN ('cell', 'section', 'card', 'record')),
            anchor_key text NULL CHECK (char_length(anchor_key) BETWEEN 1 AND 120),
            seen_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            PRIMARY KEY (tenant_id, user_id, object_kind, object_id),
            CHECK (anchor_kind = 'record' OR anchor_key IS NOT NULL)
        )
        """
    )
    op.execute(
        "CREATE INDEX presence_heartbeats_object ON presence_heartbeats "
        "(tenant_id, object_kind, object_id, seen_at DESC)"
    )
    tenant_table(op, "presence_heartbeats")
    op.execute("REVOKE UPDATE ON presence_heartbeats FROM abacus_app")
    op.execute("GRANT SELECT, INSERT, DELETE ON presence_heartbeats TO abacus_app")
    # The heartbeat's upsert moves only the anchor and the time (platform registry).
    op.execute(
        "GRANT UPDATE (anchor_kind, anchor_key, seen_at) ON presence_heartbeats TO abacus_app"
    )


def downgrade() -> None:
    op.execute("DROP TABLE presence_heartbeats")
