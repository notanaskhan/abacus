"""Idempotency keys and held delivery (P-06-T06; P-36, ADR-161).

- `idempotency_keys`: one row per (tenant, actor, route, key) holding the first response and a
  hash of its request. A retry with the same key and request gets the stored response for 24
  hours. The same key with another request is refused (422 `idempotency_key_reused`). Insert and
  read only, for the app role.
- `outbox.not_before`: an event is not delivered before this time, so a send can wait out an
  Undo window.
- `outbox.grant_id`: a grant-held effect. At delivery the relay calls the registered grant
  consumer (`consume_grant`, P-04-T10). The event goes out only if the grant is consumed then,
  and a voided grant (an Undo) delivers nothing.

Revision ID: 0099
Revises: 0098
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0099"
down_revision = "0098"
branch_labels = None
depends_on = None

_OUTBOX = ("id", "tenant_id", "event_type", "payload", "trace_context")


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE idempotency_keys (
            tenant_id uuid NOT NULL,
            actor_id text NOT NULL CHECK (length(actor_id) BETWEEN 1 AND 200),
            route text NOT NULL CHECK (length(route) BETWEEN 1 AND 200),
            key text NOT NULL CHECK (key ~ '^[A-Za-z0-9_.:-]{8,200}$'),
            request_sha256 text NOT NULL CHECK (request_sha256 ~ '^[0-9a-f]{64}$'),
            status_code integer NOT NULL CHECK (status_code BETWEEN 200 AND 299),
            response jsonb NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            expires_at timestamptz NOT NULL DEFAULT clock_timestamp() + interval '24 hours',
            PRIMARY KEY (tenant_id, actor_id, route, key)
        )
        """
    )
    op.execute("CREATE INDEX idempotency_keys_expiry ON idempotency_keys (expires_at)")
    tenant_table(op, "idempotency_keys")
    op.execute("REVOKE UPDATE, DELETE ON idempotency_keys FROM abacus_app")
    insert_columns(
        op,
        "idempotency_keys",
        ("tenant_id", "actor_id", "route", "key", "request_sha256", "status_code", "response"),
    )
    op.execute(
        "ALTER TABLE outbox ADD COLUMN not_before timestamptz NULL, ADD COLUMN grant_id uuid NULL"
    )
    insert_columns(op, "outbox", (*_OUTBOX, "not_before", "grant_id"))


def downgrade() -> None:
    insert_columns(op, "outbox", _OUTBOX)
    op.execute("ALTER TABLE outbox DROP COLUMN grant_id, DROP COLUMN not_before")
    op.execute("DROP TABLE idempotency_keys")
