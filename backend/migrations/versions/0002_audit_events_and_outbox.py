"""Audit events and outbox (ADR-007, ADR-018; TASK-006 design §3-4).

Revision ID: 0002
Revises: 0001
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_only, tenant_table

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE audit_events (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            seq bigint GENERATED ALWAYS AS IDENTITY,
            occurred_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            actor_kind text NOT NULL CHECK (actor_kind IN ('human', 'agent', 'system')),
            actor_id text NOT NULL,
            action text NOT NULL CHECK (action ~ '^[a-z][a-z_]*\\.[a-z][a-z_]*$'),
            target_type text NOT NULL,
            target_id text NOT NULL,
            before_ref jsonb NULL,
            after_ref jsonb NULL,
            trace_id text NULL,
            -- An audit event can only name the actor of the transaction that writes it.
            CONSTRAINT audit_events_actor_is_transaction_actor CHECK (
                actor_kind = current_setting('app.actor_kind', true)
                AND actor_id = current_setting('app.actor_id', true)
            )
        )
        """
    )
    op.execute("CREATE INDEX audit_events_tenant_seq ON audit_events (tenant_id, seq)")
    tenant_table(op, "audit_events")
    insert_only(op, "audit_events")

    op.execute(
        """
        CREATE TABLE outbox (
            id uuid PRIMARY KEY,
            tenant_id uuid NOT NULL,
            seq bigint GENERATED ALWAYS AS IDENTITY,
            occurred_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            event_type text NOT NULL,
            payload jsonb NOT NULL,
            published_at timestamptz NULL,
            attempts integer NOT NULL DEFAULT 0,
            last_error text NULL
        )
        """
    )
    op.execute("CREATE INDEX outbox_unpublished ON outbox (seq) WHERE published_at IS NULL")
    tenant_table(op, "outbox")
    insert_only(op, "outbox")
    # The relay (BYPASSRLS) may read the outbox and mark delivery; nothing else, anywhere.
    op.execute("GRANT SELECT ON outbox TO abacus_relay")
    op.execute("GRANT UPDATE (published_at, attempts, last_error) ON outbox TO abacus_relay")


def downgrade() -> None:
    op.execute("DROP TABLE outbox")
    op.execute("DROP TABLE audit_events")
