"""Harden audit events and outbox (TASK-006 stage 4 reviews; contract revision 1).

- The app may insert only the columns it owns: no explicit id, seq (OVERRIDING SYSTEM VALUE),
  occurred_at or delivery state.
- The actor check fails when the actor settings are unset.
- Audit targets are identifiers; relay errors are exception class names.
- Outbox key is (tenant_id, id): tenants can't collide on, or probe, each other's event IDs.
- Relay backoff via next_attempt_at.

Revision ID: 0003
Revises: 0002
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

AUDIT_COLUMNS = (
    "tenant_id",
    "actor_kind",
    "actor_id",
    "action",
    "target_type",
    "target_id",
    "before_ref",
    "after_ref",
    "trace_id",
)
OUTBOX_COLUMNS = ("id", "tenant_id", "event_type", "payload")


def upgrade() -> None:
    insert_columns(op, "audit_events", AUDIT_COLUMNS)
    insert_columns(op, "outbox", OUTBOX_COLUMNS)

    op.execute("ALTER TABLE audit_events DROP CONSTRAINT audit_events_actor_is_transaction_actor")
    op.execute(
        """
        ALTER TABLE audit_events ADD CONSTRAINT audit_events_actor_is_transaction_actor CHECK (
            actor_kind IS NOT DISTINCT FROM NULLIF(current_setting('app.actor_kind', true), '')
            AND actor_id IS NOT DISTINCT FROM NULLIF(current_setting('app.actor_id', true), '')
        )
        """
    )
    uuid = "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    op.execute(
        "ALTER TABLE audit_events ADD CONSTRAINT audit_events_target_is_identifier "
        f"CHECK (target_id ~ '^({uuid}|[0-9]+)$')"
    )

    op.execute("ALTER TABLE outbox DROP CONSTRAINT outbox_pkey")
    op.execute("ALTER TABLE outbox ADD CONSTRAINT outbox_pkey PRIMARY KEY (tenant_id, id)")
    op.execute("ALTER TABLE outbox ADD COLUMN next_attempt_at timestamptz NULL")
    op.execute(
        "ALTER TABLE outbox ADD CONSTRAINT outbox_last_error_is_class_name "
        "CHECK (last_error IS NULL OR last_error ~ '^[A-Za-z_][A-Za-z0-9_.]{0,199}$')"
    )
    op.execute("GRANT UPDATE (next_attempt_at) ON outbox TO abacus_relay")


def downgrade() -> None:
    op.execute("REVOKE UPDATE (next_attempt_at) ON outbox FROM abacus_relay")
    op.execute("ALTER TABLE outbox DROP CONSTRAINT outbox_last_error_is_class_name")
    op.execute("ALTER TABLE outbox DROP COLUMN next_attempt_at")
    op.execute("ALTER TABLE outbox DROP CONSTRAINT outbox_pkey")
    op.execute("ALTER TABLE outbox ADD CONSTRAINT outbox_pkey PRIMARY KEY (id)")
    op.execute("ALTER TABLE audit_events DROP CONSTRAINT audit_events_target_is_identifier")
    op.execute("ALTER TABLE audit_events DROP CONSTRAINT audit_events_actor_is_transaction_actor")
    op.execute(
        """
        ALTER TABLE audit_events ADD CONSTRAINT audit_events_actor_is_transaction_actor CHECK (
            actor_kind = current_setting('app.actor_kind', true)
            AND actor_id = current_setting('app.actor_id', true)
        )
        """
    )
    op.execute("REVOKE INSERT ON outbox FROM abacus_app")
    op.execute("GRANT INSERT ON outbox TO abacus_app")
    op.execute("REVOKE INSERT ON audit_events FROM abacus_app")
    op.execute("GRANT INSERT ON audit_events TO abacus_app")
