"""Trace context across the outbox (TASK-013 design §2, Q1).

- `outbox.trace_context`: the W3C `traceparent` of the transaction that emitted the event, so the
  relay continues the same trace (a retrieval and the screening it triggers share one trace ID).
  Identifiers only; the relay role already reads every outbox column.
- `audit_events.trace_id` (since 0002, filled from TASK-013): checked to be a trace ID.

Revision ID: 0011
Revises: 0010
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

OUTBOX_COLUMNS = ("id", "tenant_id", "event_type", "payload", "trace_context")
OUTBOX_COLUMNS_BEFORE = ("id", "tenant_id", "event_type", "payload")


def upgrade() -> None:
    op.execute(
        "ALTER TABLE outbox ADD COLUMN trace_context text NULL "
        "CONSTRAINT outbox_trace_context_is_traceparent "
        "CHECK (trace_context ~ '^00-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2}$')"
    )
    insert_columns(op, "outbox", OUTBOX_COLUMNS)
    op.execute(
        "ALTER TABLE audit_events ADD CONSTRAINT audit_events_trace_id_is_trace_id "
        "CHECK (trace_id ~ '^[0-9a-f]{32}$')"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE audit_events DROP CONSTRAINT audit_events_trace_id_is_trace_id")
    insert_columns(op, "outbox", OUTBOX_COLUMNS_BEFORE)
    op.execute("ALTER TABLE outbox DROP COLUMN trace_context")
