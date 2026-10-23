"""SES delivery events and per-firm email suppression (Q-01-T46), owned by `communications`.

- `message_deliveries`: what SES said happened to a send (delivered, bounced, complained, rejected,
  delayed), one row per provider event and insert-only. A redelivered event is a no-op: its
  `provider_event_id` is unique. `message_id` is the send's tag, not a foreign key. A staff
  invitation's send records no message, and its delivery events are still kept.
- `email_suppressions`: addresses the firm must not mail again after a permanent bounce or a
  complaint (or by hand). An address is stored only as an HMAC-SHA256 under the suppression
  pepper; no clear-text address is stored. At most one live suppression per address; lifting one
  stamps it, and a later bounce adds a new row.

Revision ID: 0104
Revises: 0103
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0104"
down_revision = "0103"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE message_deliveries (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            message_id uuid NOT NULL,
            provider_event_id text NOT NULL UNIQUE
                CHECK (provider_event_id ~ '^[A-Za-z0-9._:/-]{1,200}$'),
            event text NOT NULL
                CHECK (event IN ('delivered', 'bounced', 'complained', 'rejected', 'delayed')),
            bounce_kind text NULL CHECK (bounce_kind IN ('permanent', 'transient')),
            occurred_at timestamptz NOT NULL,
            recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            CHECK ((event = 'bounced') = (bounce_kind IS NOT NULL))
        )
        """
    )
    op.execute(
        "CREATE INDEX message_deliveries_by_message ON message_deliveries (tenant_id, message_id)"
    )
    tenant_table(op, "message_deliveries")
    insert_only(op, "message_deliveries")
    insert_columns(
        op,
        "message_deliveries",
        ("tenant_id", "message_id", "provider_event_id", "event", "bounce_kind", "occurred_at"),
    )
    op.execute(
        """
        CREATE FUNCTION message_deliveries_immutable() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'message_deliveries is insert-only'
                USING ERRCODE = 'insufficient_privilege';
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER message_deliveries_immutable BEFORE UPDATE OR DELETE ON "
        "message_deliveries FOR EACH ROW EXECUTE FUNCTION message_deliveries_immutable()"
    )
    op.execute(
        "CREATE TRIGGER message_deliveries_no_truncate BEFORE TRUNCATE ON message_deliveries "
        "FOR EACH STATEMENT EXECUTE FUNCTION message_deliveries_immutable()"
    )

    op.execute(
        """
        CREATE TABLE email_suppressions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            address_hash bytea NOT NULL CHECK (octet_length(address_hash) = 32),
            reason text NOT NULL CHECK (reason IN ('bounce', 'complaint', 'manual')),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            lifted_at timestamptz NULL,
            lifted_by uuid NULL,
            CHECK ((lifted_at IS NULL) = (lifted_by IS NULL))
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX email_suppressions_live ON email_suppressions "
        "(tenant_id, address_hash) WHERE lifted_at IS NULL"
    )
    tenant_table(op, "email_suppressions")
    op.execute("REVOKE UPDATE, DELETE ON email_suppressions FROM abacus_app")
    insert_columns(op, "email_suppressions", ("tenant_id", "address_hash", "reason"))
    op.execute("GRANT UPDATE (lifted_at, lifted_by) ON email_suppressions TO abacus_app")


def downgrade() -> None:
    op.execute("DROP TABLE email_suppressions")
    op.execute("DROP TABLE message_deliveries")
    op.execute("DROP FUNCTION message_deliveries_immutable()")
