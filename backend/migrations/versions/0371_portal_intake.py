"""Portal intake (N-01-T14; N-01 §3.5; ADR-137, ADR-162 §5; DEC-1060).

- `evidence_intake_object_keys`: a client's portal upload is stored in detached-key mode (ADR-162
  §5) like a client-channel evidence version, so withdrawing it can crypto-erase it. Its wrapped
  data key lives here, keyed by the intake attachment (the version table's twin; same CHECKs:
  destroyed means no wrapped key; retained and destroyed never both).
- `inbox_attachments.withdrawn_at`: when the client withdrew it; the purge erases the key 30 days
  later unless a hold covers it.
- `inbound_messages.portal_scope_kind`, `portal_scope_id`: which of the principal's grants a
  portal batch was sent under, so the principal lists its own uploads by scope.

Expand-only (Q-03-T081): a new table and nullable columns.
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0371"
down_revision = "0370"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE evidence_intake_object_keys (
            tenant_id uuid NOT NULL,
            inbox_attachment_id uuid NOT NULL,
            key_id text NOT NULL CHECK (length(key_id) BETWEEN 1 AND 300),
            wrapped_key bytea NULL CHECK (length(wrapped_key) BETWEEN 16 AND 4096),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            retained_at timestamptz NULL,
            destroyed_at timestamptz NULL,
            PRIMARY KEY (tenant_id, inbox_attachment_id),
            FOREIGN KEY (tenant_id, inbox_attachment_id)
                REFERENCES inbox_attachments (tenant_id, id),
            CONSTRAINT evidence_intake_object_keys_destroyed CHECK (
                (wrapped_key IS NULL) = (destroyed_at IS NOT NULL)
            ),
            CONSTRAINT evidence_intake_object_keys_retained_or_destroyed CHECK (
                retained_at IS NULL OR destroyed_at IS NULL
            )
        )
        """
    )
    tenant_table(op, "evidence_intake_object_keys")
    op.execute("REVOKE UPDATE, DELETE, TRUNCATE ON evidence_intake_object_keys FROM abacus_app")
    insert_columns(
        op,
        "evidence_intake_object_keys",
        ("tenant_id", "inbox_attachment_id", "key_id", "wrapped_key"),
    )
    # Erasing is one update: the key goes, the moment is stamped (the CHECK keeps them together).
    op.execute(
        "GRANT UPDATE (wrapped_key, destroyed_at, retained_at) "
        "ON evidence_intake_object_keys TO abacus_app"
    )

    op.execute("ALTER TABLE inbox_attachments ADD COLUMN withdrawn_at timestamptz NULL")
    op.execute(
        "ALTER TABLE inbox_attachments ADD CONSTRAINT inbox_attachments_withdrawn_at "
        "CHECK ((status = 'withdrawn') = (withdrawn_at IS NOT NULL))"
    )
    op.execute("GRANT UPDATE (withdrawn_at) ON inbox_attachments TO abacus_app")

    op.execute(
        "ALTER TABLE inbound_messages "
        "ADD COLUMN portal_scope_kind text NULL "
        "CHECK (portal_scope_kind IN ('client', 'client_entity', 'engagement')), "
        "ADD COLUMN portal_scope_id uuid NULL, "
        "ADD CONSTRAINT inbound_messages_portal_scope "
        "CHECK ((portal_scope_kind IS NULL) = (portal_scope_id IS NULL))"
    )
    op.execute(
        "GRANT INSERT (portal_scope_kind, portal_scope_id) ON inbound_messages TO abacus_app"
    )
    op.execute(
        "CREATE INDEX inbound_messages_by_principal ON inbound_messages "
        "(tenant_id, sender_principal_id, portal_scope_id) "
        "WHERE sender_principal_id IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX inbound_messages_by_principal")
    op.execute(
        "ALTER TABLE inbound_messages DROP CONSTRAINT inbound_messages_portal_scope, "
        "DROP COLUMN portal_scope_id, DROP COLUMN portal_scope_kind"
    )
    op.execute("ALTER TABLE inbox_attachments DROP CONSTRAINT inbox_attachments_withdrawn_at")
    op.execute("ALTER TABLE inbox_attachments DROP COLUMN withdrawn_at")
    op.execute("DROP TABLE evidence_intake_object_keys")
